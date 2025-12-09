"""FastAPI application for document processing web interface."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import Database
from .storage.config import StorageConfig
from .services.worker import WorkerManager
from .storage import get_cleanup_manager
from .routes import jobs, upload, progress, storage

logger = logging.getLogger(__name__)

# Global manager instances
worker_manager: WorkerManager = None
cleanup_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown.

    Startup sequence:
    1. Verify/create DATA_DIR
    2. Initialize storage configuration
    3. Initialize database pool with WAL mode
    4. Start background worker manager

    Shutdown sequence:
    1. Stop worker manager (graceful task completion)
    2. Close database connections

    Raises:
        DatabaseException: If database initialization fails
        OSError: If DATA_DIR cannot be created
    """
    global worker_manager

    try:
        logger.info("Starting Document Processing API")

        # Log environment diagnostics
        data_dir = os.getenv("DATA_DIR", "Data")
        data_path = Path(data_dir)
        logger.info(
            f"Environment: DATA_DIR={data_dir}, "
            f"working_directory={os.getcwd()}, "
            f"database_path={data_path / 'web.db'}"
        )

        # Check if directory exists or can be created
        if not data_path.exists():
            logger.info(f"Creating DATA_DIR: {data_path}")
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"DATA_DIR created successfully: {data_path}")
            except Exception as e:
                logger.error(f"Failed to create DATA_DIR: {e}")
                raise
        else:
            logger.info(f"DATA_DIR exists: {data_path}")

        # Initialize storage
        logger.info("Initializing storage configuration")
        StorageConfig.init()
        logger.info("Storage configuration initialized")

        # Initialize database with detailed logging
        logger.info("Initializing database")
        try:
            await Database.initialize()
            logger.info("Database initialized successfully")
        except Exception as db_error:
            logger.error(f"Database initialization failed: {db_error}", exc_info=True)
            raise

        # Initialize and start worker manager
        logger.info("Starting worker manager")
        worker_manager = WorkerManager(num_workers=1)
        await worker_manager.start()
        logger.info("Worker manager started")

        # Start cleanup manager (non-critical service)
        try:
            logger.info("Starting cleanup manager")
            cleanup_manager = get_cleanup_manager()
            await cleanup_manager.start()
            logger.info(f"Cleanup manager started (PDF: {StorageConfig.pdf_retention_hours}h, output: {StorageConfig.msf_retention_hours}h)")
        except Exception as cleanup_error:
            logger.error(f"Cleanup manager startup failed: {cleanup_error}", exc_info=True)
            # Continue without cleanup (non-critical service)

        logger.info("Document Processing API startup complete")

        yield

    except Exception as startup_error:
        logger.critical(f"Application startup failed: {startup_error}", exc_info=True)
        raise

    finally:
        # Cleanup on shutdown - use shield() to protect from cancellation
        logger.info("Shutting down Document Processing API")

        if worker_manager:
            try:
                # Shield from cancellation to ensure clean shutdown
                await asyncio.shield(worker_manager.stop())
                logger.info("Worker manager stopped")
            except asyncio.CancelledError:
                logger.warning("Worker shutdown interrupted, forcing stop")
            except Exception as e:
                logger.error(f"Error stopping workers: {e}", exc_info=True)

        # Stop cleanup manager
        if cleanup_manager:
            try:
                await asyncio.shield(cleanup_manager.stop())
                logger.info("Cleanup manager stopped")
            except asyncio.CancelledError:
                logger.warning("Cleanup manager shutdown interrupted")
            except Exception as e:
                logger.error(f"Error stopping cleanup manager: {e}", exc_info=True)

        try:
            await asyncio.shield(Database.close())
            logger.info("Database closed")
        except asyncio.CancelledError:
            logger.warning("Database close interrupted")
        except Exception as e:
            logger.error(f"Error closing database: {e}", exc_info=True)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Document Processing API",
        description="REST API for PDF document extraction and processing",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware for frontend integration
    # Read allowed origins from environment variable with secure default
    allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "https://metextractor.vercel.app,http://localhost:3000")
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers with /api prefix
    app.include_router(jobs.router, prefix="/api")
    app.include_router(upload.router, prefix="/api")
    app.include_router(progress.router, prefix="/api")
    app.include_router(storage.router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        stats = worker_manager.get_stats() if worker_manager else {}
        return {
            "status": "healthy",
            "service": "Document Processing API",
            "version": "1.0.0",
            "worker_stats": stats
        }

    @app.get("/health")
    async def health_check_root():
        """Health check endpoint (legacy, redirects to /api/health)."""
        stats = worker_manager.get_stats() if worker_manager else {}
        return {
            "status": "healthy",
            "service": "Document Processing API",
            "version": "1.0.0",
            "worker_stats": stats
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)