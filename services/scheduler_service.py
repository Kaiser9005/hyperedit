"""Scheduler service for automated video processing pipeline.

Supports two persistence modes:
- JSON file (default, offline): logs/scheduler_state.json
- Supabase (when DatabaseService provided): he_video_jobs + he_pipeline_steps
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    input_path: str
    output_dir: str
    skills: list[str]
    status: JobStatus = JobStatus.QUEUED
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    priority: int = 0  # higher = more urgent

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class SchedulerService:
    """Watch for new videos and manage processing queue."""

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

    def __init__(
        self,
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
        db=None,
    ):
        self.input_dir = Path(input_dir or os.getenv("INPUT_DIR", "input_videos"))
        self.output_dir = Path(output_dir or os.getenv("OUTPUT_DIR", "output_videos"))
        self.state_file = Path(state_file or "logs/scheduler_state.json")
        self.db = db  # Optional DatabaseService for Supabase persistence
        self._queue: list[Job] = []
        self._processed_files: set[str] = set()
        self._job_counter = 0
        self._on_job_ready: Optional[Callable[[Job], dict]] = None

        # Load previous state if exists
        self._load_state()

    def scan_for_new_files(self) -> list[Job]:
        """Scan input directory for unprocessed video files."""
        new_jobs = []
        if not self.input_dir.exists():
            return new_jobs

        for path in sorted(self.input_dir.iterdir()):
            if (
                path.is_file()
                and path.suffix.lower() in self.VIDEO_EXTENSIONS
                and str(path) not in self._processed_files
            ):
                job = self.create_job(
                    input_path=path,
                    skills=["dead_air", "captions", "audio", "color"],  # default pipeline
                )
                new_jobs.append(job)
        return new_jobs

    def create_job(
        self,
        input_path: Path,
        skills: Optional[list[str]] = None,
        priority: int = 0,
    ) -> Job:
        """Create a new processing job. Syncs to Supabase if db is available."""
        self._job_counter += 1
        job_id = f"job_{self._job_counter:04d}"
        skill_list = skills or ["dead_air", "captions", "audio"]

        # Sync to Supabase if available
        if self.db:
            try:
                db_job = self.db.create_job(
                    title=Path(input_path).stem,
                    input_path=str(input_path),
                    pipeline=skill_list,
                    priority=priority,
                )
                job_id = db_job["id"]  # Use Supabase UUID
                self.db.create_pipeline_steps(job_id, skill_list)
                logger.info(f"Job {job_id} synced to Supabase")
            except Exception as e:
                logger.warning(f"Supabase sync failed, using local: {e}")

        job = Job(
            id=job_id,
            input_path=str(input_path),
            output_dir=str(self.output_dir / Path(input_path).stem),
            skills=skill_list,
            priority=priority,
        )
        self._queue.append(job)
        self._processed_files.add(str(input_path))
        self._save_state()

        logger.info(f"Created job {job_id} for {Path(input_path).name}")
        return job

    def get_next_job(self) -> Optional[Job]:
        """Get the next queued job (highest priority first)."""
        queued = [j for j in self._queue if j.status == JobStatus.QUEUED]
        if not queued:
            return None
        # Sort by priority (descending) then by creation time (ascending)
        queued.sort(key=lambda j: (-j.priority, j.created_at))
        return queued[0]

    def start_job(self, job_id: str) -> Optional[Job]:
        """Mark a job as processing."""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.QUEUED:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now().isoformat()
            self._save_state()
            self._db_update_status(job_id, "processing")
            return job
        return None

    def complete_job(self, job_id: str, result: dict) -> Optional[Job]:
        """Mark a job as completed."""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.PROCESSING:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now().isoformat()
            job.result = result
            self._save_state()
            output_path = result.get("output_path") if isinstance(result, dict) else None
            self._db_update_status(job_id, "completed", output_path=output_path)
            return job
        return None

    def fail_job(self, job_id: str, error: str) -> Optional[Job]:
        """Mark a job as failed."""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.PROCESSING:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now().isoformat()
            job.error = error
            self._save_state()
            self._db_update_status(job_id, "failed", error_message=error)
            return job
        return None

    def cancel_job(self, job_id: str) -> Optional[Job]:
        """Cancel a queued job."""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            self._save_state()
            self._db_update_status(job_id, "cancelled")
            return job
        return None

    def _db_update_status(self, job_id: str, status: str, **kwargs) -> None:
        """Sync job status to Supabase (best-effort, non-blocking)."""
        if not self.db:
            return
        try:
            self.db.update_job_status(job_id, status, **kwargs)
        except Exception as e:
            logger.warning(f"Supabase status sync failed for {job_id}: {e}")

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        for job in self._queue:
            if job.id == job_id:
                return job
        return None

    def get_queue_status(self) -> dict:
        """Get summary of queue status."""
        status_counts = {}
        for status in JobStatus:
            status_counts[status.value] = sum(
                1 for j in self._queue if j.status == status
            )
        return {
            "total_jobs": len(self._queue),
            "by_status": status_counts,
            "processed_files": len(self._processed_files),
        }

    def set_job_handler(self, handler: Callable[[Job], dict]) -> None:
        """Set the callback function that processes jobs."""
        self._on_job_ready = handler

    def process_next(self) -> Optional[dict]:
        """Process the next available job using the registered handler."""
        if not self._on_job_ready:
            raise RuntimeError("No job handler registered. Call set_job_handler() first.")

        job = self.get_next_job()
        if not job:
            return None

        self.start_job(job.id)
        try:
            result = self._on_job_ready(job)
            self.complete_job(job.id, result)
            return {"job_id": job.id, "status": "completed", "result": result}
        except Exception as e:
            self.fail_job(job.id, str(e))
            return {"job_id": job.id, "status": "failed", "error": str(e)}

    def _save_state(self) -> None:
        """Persist scheduler state to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "job_counter": self._job_counter,
            "processed_files": list(self._processed_files),
            "queue": [
                {
                    "id": j.id,
                    "input_path": j.input_path,
                    "output_dir": j.output_dir,
                    "skills": j.skills,
                    "status": j.status.value,
                    "created_at": j.created_at,
                    "started_at": j.started_at,
                    "completed_at": j.completed_at,
                    "result": j.result,
                    "error": j.error,
                    "priority": j.priority,
                }
                for j in self._queue
            ],
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> None:
        """Load scheduler state from JSON file."""
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file) as f:
                state = json.load(f)
            self._job_counter = state.get("job_counter", 0)
            self._processed_files = set(state.get("processed_files", []))
            for jdata in state.get("queue", []):
                job = Job(
                    id=jdata["id"],
                    input_path=jdata["input_path"],
                    output_dir=jdata["output_dir"],
                    skills=jdata["skills"],
                    status=JobStatus(jdata["status"]),
                    created_at=jdata.get("created_at", ""),
                    started_at=jdata.get("started_at"),
                    completed_at=jdata.get("completed_at"),
                    result=jdata.get("result"),
                    error=jdata.get("error"),
                    priority=jdata.get("priority", 0),
                )
                self._queue.append(job)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load scheduler state: {e}")
