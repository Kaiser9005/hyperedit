"""Database service for HyperEdit AI — Supabase persistence layer.

Replaces JSON file persistence with proper PostgreSQL storage via Supabase.
All tables use the `he_` prefix to isolate from FOFAL ERP tables in the
shared Supabase project.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy-load Supabase client to allow mocking in tests.

    Uses service_role key (bypasses RLS) since HyperEdit is a server-side
    batch processor. Falls back to anon key if service_role not set.
    """
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set in .env"
        )
    return create_client(url, key)


class DatabaseService:
    """Supabase persistence for HyperEdit video jobs and pipeline data.

    Provides CRUD operations for all 8 he_* tables. Each method maps
    directly to a database operation — no caching, no in-memory state.
    """

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = _get_client()
        return self._client

    # ── Video Jobs ──────────────────────────────────────────────

    def create_job(
        self,
        title: str,
        input_path: str,
        pipeline: list[str],
        config: Optional[dict] = None,
        priority: int = 0,
        max_retries: int = 3,
    ) -> dict:
        """Create a new video job in queued status."""
        data = {
            "title": title,
            "status": "queued",
            "input_path": input_path,
            "pipeline": pipeline,
            "config": config or {},
            "priority": priority,
            "retry_count": 0,
            "max_retries": max_retries,
        }
        result = (
            self.client.table("he_video_jobs")
            .insert(data)
            .execute()
        )
        return result.data[0]

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID."""
        result = (
            self.client.table("he_video_jobs")
            .select("*")
            .eq("id", job_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_next_job(self) -> Optional[dict]:
        """Get the highest-priority queued job."""
        result = (
            self.client.table("he_video_jobs")
            .select("*")
            .eq("status", "queued")
            .order("priority", desc=True)
            .order("created_at")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        output_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[dict]:
        """Update job status with optional output path and error."""
        data: dict = {"status": status}
        now = datetime.now(timezone.utc).isoformat()

        if status == "processing":
            data["started_at"] = now
        elif status in ("completed", "failed", "cancelled"):
            data["completed_at"] = now

        if output_path is not None:
            data["output_path"] = output_path
        if error_message is not None:
            data["error_message"] = error_message

        result = (
            self.client.table("he_video_jobs")
            .update(data)
            .eq("id", job_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def increment_retry(self, job_id: str) -> Optional[dict]:
        """Increment retry count and re-queue if under max_retries."""
        job = self.get_job(job_id)
        if not job:
            return None

        new_count = job["retry_count"] + 1
        if new_count >= job["max_retries"]:
            return self.update_job_status(
                job_id, "failed", error_message="Max retries exceeded"
            )

        result = (
            self.client.table("he_video_jobs")
            .update({"retry_count": new_count, "status": "queued", "error_message": None})
            .eq("id", job_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List jobs with optional status filter."""
        query = (
            self.client.table("he_video_jobs")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if status:
            query = query.eq("status", status)
        return query.execute().data

    def get_queue_status(self) -> dict:
        """Get job count grouped by status."""
        result = (
            self.client.table("he_video_jobs")
            .select("status")
            .execute()
        )
        counts: dict[str, int] = {}
        for row in result.data:
            s = row["status"]
            counts[s] = counts.get(s, 0) + 1
        return {
            "total_jobs": len(result.data),
            "by_status": counts,
        }

    # ── Pipeline Steps ──────────────────────────────────────────

    def create_pipeline_steps(self, job_id: str, skills: list[str], configs: Optional[dict] = None) -> list[dict]:
        """Create pipeline step rows for a job (one per skill in order)."""
        configs = configs or {}
        rows = [
            {
                "job_id": job_id,
                "skill_name": skill,
                "step_order": i,
                "config": configs.get(skill, {}),
            }
            for i, skill in enumerate(skills)
        ]
        result = self.client.table("he_pipeline_steps").insert(rows).execute()
        return result.data

    def get_pipeline_steps(self, job_id: str) -> list[dict]:
        """Get all steps for a job, ordered by step_order."""
        result = (
            self.client.table("he_pipeline_steps")
            .select("*")
            .eq("job_id", job_id)
            .order("step_order")
            .execute()
        )
        return result.data

    def update_step(
        self,
        step_id: str,
        status: str,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None,
        result_data: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[dict]:
        """Update a pipeline step's status and results."""
        data: dict = {"status": status}
        now = datetime.now(timezone.utc).isoformat()

        if status == "running":
            data["started_at"] = now
        elif status in ("completed", "failed", "skipped"):
            data["completed_at"] = now

        if input_path is not None:
            data["input_path"] = input_path
        if output_path is not None:
            data["output_path"] = output_path
        if result_data is not None:
            data["result"] = result_data
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        if error_message is not None:
            data["error_message"] = error_message

        result = (
            self.client.table("he_pipeline_steps")
            .update(data)
            .eq("id", step_id)
            .execute()
        )
        return result.data[0] if result.data else None

    # ── Video Metadata ──────────────────────────────────────────

    def save_metadata(
        self,
        file_path: str,
        metadata: dict,
        job_id: Optional[str] = None,
    ) -> dict:
        """Save video metadata (from FFprobe)."""
        data = {
            "file_path": file_path,
            "job_id": job_id,
            "duration": metadata.get("duration"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "fps": metadata.get("fps"),
            "codec": metadata.get("codec"),
            "bitrate": metadata.get("bitrate"),
            "file_size_bytes": metadata.get("file_size") or metadata.get("file_size_bytes"),
            "has_audio": metadata.get("has_audio"),
            "audio_codec": metadata.get("audio_codec"),
            "audio_sample_rate": metadata.get("audio_sample_rate"),
            "raw_metadata": metadata.get("raw_metadata"),
        }
        result = self.client.table("he_video_metadata").insert(data).execute()
        return result.data[0]

    def get_metadata(self, file_path: str) -> Optional[dict]:
        """Get cached metadata for a file path."""
        result = (
            self.client.table("he_video_metadata")
            .select("*")
            .eq("file_path", file_path)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # ── Pipeline Assets ─────────────────────────────────────────

    def save_asset(
        self,
        job_id: str,
        asset_type: str,
        file_path: str,
        file_size_bytes: Optional[int] = None,
        mime_type: Optional[str] = None,
        step_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Record a generated asset (thumbnail, GIF, caption file, etc.)."""
        data = {
            "job_id": job_id,
            "step_id": step_id,
            "asset_type": asset_type,
            "file_path": file_path,
            "file_size_bytes": file_size_bytes,
            "mime_type": mime_type,
            "metadata": metadata or {},
        }
        result = self.client.table("he_pipeline_assets").insert(data).execute()
        return result.data[0]

    def get_assets(self, job_id: str, asset_type: Optional[str] = None) -> list[dict]:
        """Get assets for a job, optionally filtered by type."""
        query = (
            self.client.table("he_pipeline_assets")
            .select("*")
            .eq("job_id", job_id)
        )
        if asset_type:
            query = query.eq("asset_type", asset_type)
        return query.execute().data

    # ── Brand Kits ──────────────────────────────────────────────

    def get_default_brand_kit(self) -> Optional[dict]:
        """Get the default brand kit."""
        result = (
            self.client.table("he_brand_kits")
            .select("*")
            .eq("is_default", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_brand_kit(self, name: str) -> Optional[dict]:
        """Get a brand kit by name."""
        result = (
            self.client.table("he_brand_kits")
            .select("*")
            .eq("name", name)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_brand_kits(self) -> list[dict]:
        """List all brand kits."""
        return self.client.table("he_brand_kits").select("*").execute().data

    def upsert_brand_kit(self, data: dict) -> dict:
        """Create or update a brand kit."""
        result = (
            self.client.table("he_brand_kits")
            .upsert(data, on_conflict="name")
            .execute()
        )
        return result.data[0]

    # ── Video Templates ─────────────────────────────────────────

    def get_template(self, name: str) -> Optional[dict]:
        """Get a template by name."""
        result = (
            self.client.table("he_video_templates")
            .select("*")
            .eq("name", name)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_templates(self, system_only: bool = False) -> list[dict]:
        """List all templates."""
        query = self.client.table("he_video_templates").select("*")
        if system_only:
            query = query.eq("is_system", True)
        return query.order("name").execute().data

    def increment_template_usage(self, template_id: str) -> None:
        """Increment usage_count for a template."""
        tmpl = (
            self.client.table("he_video_templates")
            .select("usage_count")
            .eq("id", template_id)
            .execute()
        )
        if tmpl.data:
            new_count = tmpl.data[0]["usage_count"] + 1
            (
                self.client.table("he_video_templates")
                .update({"usage_count": new_count})
                .eq("id", template_id)
                .execute()
            )

    # ── QA Results ──────────────────────────────────────────────

    def save_qa_results(
        self,
        job_id: str,
        results: list[dict],
        step_id: Optional[str] = None,
    ) -> list[dict]:
        """Save QA check results for a job/step."""
        rows = [
            {
                "job_id": job_id,
                "step_id": step_id,
                "check_name": r.get("check_name", "unknown"),
                "passed": r.get("passed", False),
                "severity": r.get("severity", "info"),
                "message": r.get("message"),
                "expected_value": r.get("expected_value"),
                "actual_value": r.get("actual_value"),
            }
            for r in results
        ]
        result = self.client.table("he_qa_results").insert(rows).execute()
        return result.data

    def get_qa_results(self, job_id: str) -> list[dict]:
        """Get all QA results for a job."""
        return (
            self.client.table("he_qa_results")
            .select("*")
            .eq("job_id", job_id)
            .order("created_at")
            .execute()
            .data
        )

    # ── Notification Logs ───────────────────────────────────────

    def log_notification(
        self,
        channel: str,
        message: str,
        status: str = "sent",
        job_id: Optional[str] = None,
        response: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> dict:
        """Log a sent or failed notification."""
        data = {
            "channel": channel,
            "message": message,
            "status": status,
            "job_id": job_id,
            "response": response,
            "error_message": error_message,
        }
        result = self.client.table("he_notification_logs").insert(data).execute()
        return result.data[0]

    def get_notifications(self, job_id: str) -> list[dict]:
        """Get notification history for a job."""
        return (
            self.client.table("he_notification_logs")
            .select("*")
            .eq("job_id", job_id)
            .order("created_at")
            .execute()
            .data
        )
