"""Job service layer for CRUD operations.

Implements business logic and database operations for job management.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from ..core.database import Database, transaction
from ..common.exceptions import (
    JobNotFoundException,
    JobStateException,
    DatabaseException,
    ValidationException
)
from .schemas import (
    JobCreate,
    JobUpdate,
    JobInDB,
    JobStatus,
    JobStage,
    JobListResponse
)

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing job operations."""

    @staticmethod
    async def create_job(job_data: JobCreate) -> JobInDB:
        """Create a new job in the database."""
        job_id = str(uuid4())
        pool = Database.get_pool()

        try:
            async with pool.acquire() as conn:
                async with transaction(conn):
                    # Use metadata and output_formats from job_data
                    metadata = job_data.metadata or {}
                    output_formats = job_data.output_formats or ["msf"]

                    # Insert job
                    await conn.execute(
                        """
                        INSERT INTO jobs (
                            id, filename, file_size, mime_type,
                            pdf_path, status, current_stage,
                            created_at, metadata, output_formats
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            job_data.filename,
                            job_data.file_size,
                            job_data.mime_type,
                            job_data.pdf_path,
                            JobStatus.PENDING.value,
                            JobStage.QUEUED.value,
                            datetime.now(timezone.utc).isoformat(),
                            json.dumps(metadata),
                            json.dumps(output_formats)
                        )
                    )

                    # Log event
                    await conn.execute(
                        """
                        INSERT INTO job_events (job_id, event_type, message)
                        VALUES (?, ?, ?)
                        """,
                        (job_id, "created", f"Job created for {job_data.filename}")
                    )

            # Retrieve and return created job
            job = await JobService.get_job(UUID(job_id))
            logger.info(f"Created job {job_id} for file {job_data.filename}")
            return job

        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise DatabaseException(f"Failed to create job: {e}")

    @staticmethod
    async def get_job(job_id: UUID) -> JobInDB:
        """Get a job by ID."""
        pool = Database.get_pool()

        try:
            async with pool.acquire() as conn:
                cursor = await conn.execute(
                    "SELECT * FROM jobs WHERE id = ?",
                    (str(job_id),)
                )
                row = await cursor.fetchone()

                if not row:
                    raise JobNotFoundException(f"Job {job_id} not found")

                # Convert row to dict and parse
                job_dict = dict(row)
                job_dict["id"] = UUID(job_dict["id"])
                job_dict["metadata"] = json.loads(job_dict.get("metadata", "{}"))
                job_dict["source_pages"] = json.loads(job_dict.get("source_pages", "[]"))

                # Parse multi-format output fields
                job_dict["output_formats"] = json.loads(
                    job_dict.get("output_formats", '["msf"]')
                )
                job_dict["acc_paths"] = json.loads(
                    job_dict.get("acc_paths", "{}")
                )

                # Parse timestamps
                for field in ["created_at", "started_at", "completed_at"]:
                    if job_dict.get(field):
                        job_dict[field] = datetime.fromisoformat(job_dict[field])

                return JobInDB(**job_dict)

        except JobNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise DatabaseException(f"Failed to get job: {e}")

    @staticmethod
    async def update_job(job_id: UUID, update_data: JobUpdate) -> JobInDB:
        """Update a job's status and metadata."""
        pool = Database.get_pool()

        try:
            # Get current job state
            current_job = await JobService.get_job(job_id)

            # Validate state transition
            if current_job.is_terminal and update_data.status:
                raise JobStateException(
                    f"Cannot update job in terminal state {current_job.status}"
                )

            async with pool.acquire() as conn:
                async with transaction(conn):
                    # Build update query dynamically
                    updates = []
                    params = []

                    if update_data.status is not None:
                        updates.append("status = ?")
                        params.append(update_data.status.value)

                        if update_data.status == JobStatus.PROCESSING:
                            updates.append("started_at = ?")
                            params.append(datetime.now(timezone.utc).isoformat())
                        elif update_data.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                            if not current_job.started_at:
                                updates.append("started_at = ?")
                                params.append(datetime.now(timezone.utc).isoformat())
                            updates.append("completed_at = ?")
                            params.append(datetime.now(timezone.utc).isoformat())

                    if update_data.progress is not None:
                        updates.append("progress = ?")
                        params.append(update_data.progress)

                    if update_data.current_stage is not None:
                        updates.append("current_stage = ?")
                        params.append(update_data.current_stage.value)

                    if update_data.msf_path is not None:
                        updates.append("msf_path = ?")
                        params.append(update_data.msf_path)

                    if update_data.error is not None:
                        updates.append("error = ?")
                        params.append(update_data.error)

                    if update_data.metadata is not None:
                        # Merge metadata
                        current_meta = current_job.metadata if current_job.metadata else {}
                        current_meta.update(update_data.metadata)
                        updates.append("metadata = ?")
                        # Ensure metadata is JSON serializable
                        serializable_meta = {}
                        for key, value in current_meta.items():
                            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                                serializable_meta[key] = value
                            else:
                                serializable_meta[key] = str(value)
                        params.append(json.dumps(serializable_meta))

                    # Multi-format output fields
                    if update_data.output_formats is not None:
                        updates.append("output_formats = ?")
                        params.append(json.dumps(update_data.output_formats))

                    if update_data.acc_paths is not None:
                        # Merge ACC paths with existing
                        current_acc = current_job.acc_paths if current_job.acc_paths else {}
                        current_acc.update(update_data.acc_paths)
                        updates.append("acc_paths = ?")
                        params.append(json.dumps(current_acc))

                    # Execute update
                    if updates:
                        params.append(str(job_id))
                        await conn.execute(
                            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
                            params
                        )

                        # Log status change event
                        if update_data.status:
                            await conn.execute(
                                """
                                INSERT INTO job_events (job_id, event_type, message, details)
                                VALUES (?, ?, ?, ?)
                                """,
                                (
                                    str(job_id),
                                    "status_change",
                                    f"Status changed to {update_data.status.value}",
                                    json.dumps({"from": current_job.status.value, "to": update_data.status.value})
                                )
                            )

            # Return updated job
            updated_job = await JobService.get_job(job_id)
            logger.info(f"Updated job {job_id}")
            return updated_job

        except (JobNotFoundException, JobStateException):
            raise
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise DatabaseException(f"Failed to update job: {e}")

    @staticmethod
    async def list_jobs(
        page: int = 1,
        per_page: int = 50,
        status: Optional[JobStatus] = None,
        search: Optional[str] = None
    ) -> JobListResponse:
        """List jobs with pagination and filtering."""
        if page < 1:
            raise ValidationException("Page must be >= 1")
        if per_page < 1 or per_page > 100:
            raise ValidationException("Per page must be between 1 and 100")

        pool = Database.get_pool()
        offset = (page - 1) * per_page

        try:
            async with pool.acquire() as conn:
                # Build query with filters
                where_clauses = []
                params = []

                if status:
                    where_clauses.append("status = ?")
                    params.append(status.value)

                if search:
                    where_clauses.append("filename LIKE ?")
                    params.append(f"%{search}%")

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                # Get total count
                count_query = f"SELECT COUNT(*) as total FROM jobs {where_sql}"
                cursor = await conn.execute(count_query, params)
                total = (await cursor.fetchone())["total"]

                # Get paginated jobs
                list_query = f"""
                    SELECT * FROM jobs
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([per_page, offset])
                cursor = await conn.execute(list_query, params)
                rows = await cursor.fetchall()

                # Convert rows to JobInDB objects
                jobs = []
                for row in rows:
                    job_dict = dict(row)
                    job_dict["id"] = UUID(job_dict["id"])
                    job_dict["metadata"] = json.loads(job_dict.get("metadata", "{}"))
                    job_dict["source_pages"] = json.loads(job_dict.get("source_pages", "[]"))

                    # Parse multi-format output fields
                    job_dict["output_formats"] = json.loads(
                        job_dict.get("output_formats", '["msf"]')
                    )
                    job_dict["acc_paths"] = json.loads(
                        job_dict.get("acc_paths", "{}")
                    )

                    # Parse timestamps
                    for field in ["created_at", "started_at", "completed_at"]:
                        if job_dict.get(field):
                            job_dict[field] = datetime.fromisoformat(job_dict[field])

                    jobs.append(JobInDB(**job_dict))

                return JobListResponse(
                    jobs=jobs,
                    total=total,
                    page=page,
                    per_page=per_page
                )

        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            raise DatabaseException(f"Failed to list jobs: {e}")

    @staticmethod
    async def delete_job(job_id: UUID, hard_delete: bool = False) -> bool:
        """Delete or cancel a job."""
        pool = Database.get_pool()

        try:
            job = await JobService.get_job(job_id)

            async with pool.acquire() as conn:
                async with transaction(conn):
                    if hard_delete:
                        # Permanently delete
                        await conn.execute(
                            "DELETE FROM jobs WHERE id = ?",
                            (str(job_id),)
                        )
                        logger.info(f"Hard deleted job {job_id}")
                    else:
                        # Soft delete - mark as cancelled
                        if not job.can_cancel:
                            raise JobStateException(
                                f"Cannot cancel job in state {job.status}"
                            )

                        now = datetime.now(timezone.utc).isoformat()
                        await conn.execute(
                            """
                            UPDATE jobs
                            SET status = ?,
                                started_at = COALESCE(started_at, ?),
                                completed_at = ?,
                                error = ?
                            WHERE id = ?
                            """,
                            (
                                JobStatus.CANCELLED.value,
                                now,
                                now,
                                "Job cancelled by user",
                                str(job_id)
                            )
                        )

                        await conn.execute(
                            """
                            INSERT INTO job_events (job_id, event_type, message)
                            VALUES (?, ?, ?)
                            """,
                            (str(job_id), "cancelled", "Job cancelled by user")
                        )

                        logger.info(f"Cancelled job {job_id}")

            return True

        except (JobNotFoundException, JobStateException):
            raise
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            raise DatabaseException(f"Failed to delete job: {e}")

    @staticmethod
    async def cleanup_old_jobs(hours: int = 24) -> int:
        """Clean up old completed jobs."""
        pool = Database.get_pool()

        try:
            async with pool.acquire() as conn:
                async with transaction(conn):
                    cursor = await conn.execute(
                        """
                        DELETE FROM jobs
                        WHERE status IN ('completed', 'failed', 'cancelled')
                        AND datetime(completed_at) < datetime('now', ? || ' hours')
                        """,
                        (-hours,)
                    )

                    deleted = cursor.rowcount
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old jobs")

                    return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            raise DatabaseException(f"Failed to cleanup jobs: {e}")

    @staticmethod
    async def get_pending_job() -> Optional[JobInDB]:
        """Get the next pending job for processing."""
        pool = Database.get_pool()

        try:
            async with pool.acquire() as conn:
                cursor = await conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (JobStatus.PENDING.value,)
                )
                row = await cursor.fetchone()

                if not row:
                    return None

                # Convert and return
                job_dict = dict(row)
                job_dict["id"] = UUID(job_dict["id"])
                job_dict["metadata"] = json.loads(job_dict.get("metadata", "{}"))
                job_dict["source_pages"] = json.loads(job_dict.get("source_pages", "[]"))

                # Parse multi-format output fields
                job_dict["output_formats"] = json.loads(
                    job_dict.get("output_formats", '["msf"]')
                )
                job_dict["acc_paths"] = json.loads(
                    job_dict.get("acc_paths", "{}")
                )

                for field in ["created_at", "started_at", "completed_at"]:
                    if job_dict.get(field):
                        job_dict[field] = datetime.fromisoformat(job_dict[field])

                return JobInDB(**job_dict)

        except Exception as e:
            logger.error(f"Failed to get pending job: {e}")
            raise DatabaseException(f"Failed to get pending job: {e}")