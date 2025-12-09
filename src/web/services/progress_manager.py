"""Progress event management for real-time updates."""

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    """Progress event data."""
    job_id: str
    timestamp: datetime
    progress: int
    phase: str
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "timestamp": self.timestamp.isoformat(),
            "progress": self.progress,
            "phase": self.phase,
            "stage": self.phase,  # Frontend expects 'stage', send both for compatibility
            "message": self.message,
            "details": self.details
        }

    def to_sse(self) -> str:
        """Format as SSE data."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


class ProgressManager:
    """Manages progress events for all jobs."""

    def __init__(self, max_events_per_job: int = 100):
        """
        Initialize progress manager.

        Args:
            max_events_per_job: Maximum events to store per job
        """
        self.max_events_per_job = max_events_per_job
        self._events: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_events_per_job)
        )
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

        logger.info(f"Progress manager initialized (max {max_events_per_job} events/job)")

    async def add_event(
        self,
        job_id: str,
        progress: int,
        phase: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a progress event.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            phase: Current processing phase
            message: Optional descriptive message
            details: Optional additional details
        """
        # Generate default message if not provided
        if message is None:
            message = self._generate_message(phase, progress, details)

        # Create event
        event = ProgressEvent(
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            progress=progress,
            phase=phase,
            message=message,
            details=details or {}
        )

        async with self._lock:
            # Store event
            self._events[job_id].append(event)

            # Notify subscribers
            if job_id in self._subscribers:
                dead_queues = []
                for queue in self._subscribers[job_id]:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning(f"Queue full for job {job_id}, dropping event")
                    except Exception as e:
                        logger.error(f"Failed to notify subscriber: {e}")
                        dead_queues.append(queue)

                # Remove dead queues
                for queue in dead_queues:
                    self._subscribers[job_id].remove(queue)

        logger.debug(f"Progress event: job={job_id}, phase={phase}, progress={progress}%")

    def _generate_message(
        self,
        phase: str,
        progress: int,
        details: Optional[Dict[str, Any]]
    ) -> str:
        """Generate descriptive message for phase."""
        messages = {
            "toc_analysis": "Analyzing document structure",
            "table_extraction": "Extracting specification tables",
            "vision_processing": "Processing table images with vision AI",
            "llm_extraction": "Extracting specifications with AI",
            "msf_generation": "Generating MSF output",
            "complete": "Processing complete",
            "error": "Processing failed"
        }

        base_message = messages.get(phase, f"Processing ({phase})")

        # Add detail information if available
        if details:
            if "tables_done" in details and "tables_total" in details:
                base_message += f" ({details['tables_done']}/{details['tables_total']} tables)"
            elif "pages_done" in details and "pages_total" in details:
                base_message += f" ({details['pages_done']}/{details['pages_total']} pages)"

        return base_message

    async def subscribe(
        self,
        job_id: str,
        include_history: bool = True
    ) -> AsyncGenerator[ProgressEvent, None]:
        """
        Subscribe to progress events for a job.

        Args:
            job_id: Job identifier
            include_history: Include historical events

        Yields:
            Progress events as they occur
        """
        queue = asyncio.Queue(maxsize=50)

        async with self._lock:
            # Send historical events if requested
            if include_history and job_id in self._events:
                for event in self._events[job_id]:
                    yield event

            # Register subscriber
            self._subscribers[job_id].append(queue)

        try:
            # Stream new events
            while True:
                event = await queue.get()
                yield event

                # Stop on completion or error
                if event.phase in ("complete", "error"):
                    break

        finally:
            # Unsubscribe
            async with self._lock:
                if job_id in self._subscribers:
                    try:
                        self._subscribers[job_id].remove(queue)
                    except ValueError:
                        pass  # Already removed

    async def get_events(
        self,
        job_id: str,
        since_timestamp: Optional[datetime] = None
    ) -> List[ProgressEvent]:
        """
        Get historical events for a job.

        Args:
            job_id: Job identifier
            since_timestamp: Only return events after this timestamp

        Returns:
            List of progress events
        """
        async with self._lock:
            if job_id not in self._events:
                return []

            events = list(self._events[job_id])

            if since_timestamp:
                events = [
                    e for e in events
                    if e.timestamp > since_timestamp
                ]

            return events

    async def get_latest_progress(self, job_id: str) -> Optional[int]:
        """
        Get latest progress percentage for a job.

        Args:
            job_id: Job identifier

        Returns:
            Latest progress percentage or None
        """
        async with self._lock:
            if job_id not in self._events or not self._events[job_id]:
                return None

            return self._events[job_id][-1].progress

    async def clear_job_events(self, job_id: str) -> None:
        """
        Clear events for a specific job.

        Args:
            job_id: Job identifier
        """
        async with self._lock:
            if job_id in self._events:
                del self._events[job_id]
            if job_id in self._subscribers:
                # Close all subscriber queues
                for queue in self._subscribers[job_id]:
                    try:
                        queue.put_nowait(None)  # Signal close
                    except Exception as e:
                        logger.debug(f"Failed to signal close to queue: {e}")
                del self._subscribers[job_id]

        logger.debug(f"Cleared events for job {job_id}")

    async def cleanup_old_events(self, keep_hours: int = 24) -> int:
        """
        Clean up events older than specified hours.

        Args:
            keep_hours: Hours to keep events

        Returns:
            Number of jobs cleaned
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
        cleaned = 0

        async with self._lock:
            jobs_to_clean = []

            for job_id, events in self._events.items():
                if events and events[-1].timestamp < cutoff:
                    # Check if job has active subscribers
                    if job_id not in self._subscribers or not self._subscribers[job_id]:
                        jobs_to_clean.append(job_id)

            for job_id in jobs_to_clean:
                del self._events[job_id]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up events for {cleaned} old jobs")

        return cleaned

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_jobs": len(self._events),
            "total_events": sum(len(events) for events in self._events.values()),
            "active_subscribers": sum(len(subs) for subs in self._subscribers.values()),
            "max_events_per_job": self.max_events_per_job
        }