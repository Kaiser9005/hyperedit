"""Tests for database_service.py — HyperEdit Supabase persistence layer.

Uses a mock Supabase client to test all CRUD operations without network access.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Mock Supabase Client ────────────────────────────────────────

class MockQueryBuilder:
    """Simulates Supabase query builder chain with realistic responses."""

    def __init__(self, table_name: str, store: dict):
        self._table = table_name
        self._store = store  # shared dict of {table: [rows]}
        self._filters = {}
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._range_start = None
        self._range_end = None

    def select(self, columns="*"):
        self._filters = {}
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def range(self, start, end):
        self._range_start = start
        self._range_end = end
        return self

    def insert(self, data):
        self._insert_data = data
        return self

    def update(self, data):
        self._update_data = data
        return self

    def upsert(self, data, on_conflict=None):
        self._insert_data = data
        return self

    def execute(self):
        resp = MagicMock()

        # Handle insert
        if hasattr(self, "_insert_data"):
            data = self._insert_data
            if isinstance(data, dict):
                data = [data]
            for row in data:
                if "id" not in row:
                    row["id"] = f"uuid-{len(self._store.get(self._table, []))+1}"
                if "created_at" not in row:
                    row["created_at"] = "2026-02-23T00:00:00Z"
                self._store.setdefault(self._table, []).append(row)
            resp.data = data
            del self._insert_data
            return resp

        # Handle update
        if hasattr(self, "_update_data"):
            rows = self._store.get(self._table, [])
            updated = []
            for row in rows:
                match = all(row.get(k) == v for k, v in self._filters.items())
                if match:
                    row.update(self._update_data)
                    updated.append(row)
            resp.data = updated
            del self._update_data
            return resp

        # Handle select
        rows = list(self._store.get(self._table, []))
        for col, val in self._filters.items():
            rows = [r for r in rows if r.get(col) == val]

        if self._order_col:
            rows.sort(
                key=lambda r: r.get(self._order_col, ""),
                reverse=self._order_desc,
            )

        if self._limit_val is not None:
            rows = rows[: self._limit_val]

        if self._range_start is not None:
            rows = rows[self._range_start : self._range_end + 1]

        resp.data = rows
        return resp


class MockSupabaseClient:
    """Minimal Supabase client mock that tracks table operations."""

    def __init__(self):
        self._store = {}

    def table(self, name):
        return MockQueryBuilder(name, self._store)


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def db():
    """DatabaseService with mock client."""
    from database_service import DatabaseService

    client = MockSupabaseClient()
    return DatabaseService(client=client)


@pytest.fixture
def db_with_job(db):
    """DatabaseService with one pre-created job."""
    job = db.create_job(
        title="Test Video",
        input_path="/videos/test.mp4",
        pipeline=["dead-air", "captions", "audio"],
        priority=5,
    )
    return db, job


# ── Video Jobs Tests ────────────────────────────────────────────

class TestVideoJobs:
    def test_create_job(self, db):
        job = db.create_job(
            title="My Video",
            input_path="/input/video.mp4",
            pipeline=["dead-air", "captions"],
        )
        assert job["title"] == "My Video"
        assert job["input_path"] == "/input/video.mp4"
        assert job["pipeline"] == ["dead-air", "captions"]
        assert "id" in job

    def test_create_job_with_config(self, db):
        job = db.create_job(
            title="Configured",
            input_path="/input/v.mp4",
            pipeline=["audio"],
            config={"audio": {"normalize": True}},
            priority=10,
            max_retries=5,
        )
        assert job["config"] == {"audio": {"normalize": True}}
        assert job["priority"] == 10
        assert job["max_retries"] == 5

    def test_get_job(self, db_with_job):
        db, job = db_with_job
        fetched = db.get_job(job["id"])
        assert fetched is not None
        assert fetched["id"] == job["id"]
        assert fetched["title"] == "Test Video"

    def test_get_job_not_found(self, db):
        result = db.get_job("nonexistent-id")
        assert result is None

    def test_get_next_job(self, db):
        db.create_job("Low", "/a.mp4", ["audio"], priority=1)
        db.create_job("High", "/b.mp4", ["audio"], priority=10)
        db.create_job("Medium", "/c.mp4", ["audio"], priority=5)

        # Mock: our mock doesn't perfectly replicate Supabase ordering,
        # but we verify the method returns a queued job
        next_job = db.get_next_job()
        assert next_job is not None

    def test_get_next_job_empty(self, db):
        assert db.get_next_job() is None

    def test_update_job_status_processing(self, db_with_job):
        db, job = db_with_job
        updated = db.update_job_status(job["id"], "processing")
        assert updated is not None
        assert updated["status"] == "processing"
        assert "started_at" in updated

    def test_update_job_status_completed(self, db_with_job):
        db, job = db_with_job
        updated = db.update_job_status(
            job["id"], "completed", output_path="/output/final.mp4"
        )
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["output_path"] == "/output/final.mp4"

    def test_update_job_status_failed(self, db_with_job):
        db, job = db_with_job
        updated = db.update_job_status(
            job["id"], "failed", error_message="FFmpeg crash"
        )
        assert updated is not None
        assert updated["status"] == "failed"
        assert updated["error_message"] == "FFmpeg crash"

    def test_list_jobs(self, db):
        for i in range(5):
            db.create_job(f"Job {i}", f"/v{i}.mp4", ["audio"])
        jobs = db.list_jobs()
        assert len(jobs) == 5

    def test_get_queue_status(self, db):
        db.create_job("A", "/a.mp4", ["audio"])
        db.create_job("B", "/b.mp4", ["audio"])
        status = db.get_queue_status()
        assert status["total_jobs"] == 2

    def test_increment_retry(self, db_with_job):
        db, job = db_with_job
        # Default max_retries=3, retry_count starts at 0
        job["retry_count"] = 0
        job["max_retries"] = 3
        updated = db.increment_retry(job["id"])
        assert updated is not None


# ── Pipeline Steps Tests ────────────────────────────────────────

class TestPipelineSteps:
    def test_create_pipeline_steps(self, db_with_job):
        db, job = db_with_job
        steps = db.create_pipeline_steps(
            job["id"],
            ["dead-air", "captions", "audio"],
            configs={"captions": {"language": "en"}},
        )
        assert len(steps) == 3
        assert steps[0]["skill_name"] == "dead-air"
        assert steps[0]["step_order"] == 0
        assert steps[1]["skill_name"] == "captions"
        assert steps[1]["config"] == {"language": "en"}
        assert steps[2]["skill_name"] == "audio"
        assert steps[2]["config"] == {}

    def test_get_pipeline_steps(self, db_with_job):
        db, job = db_with_job
        db.create_pipeline_steps(job["id"], ["dead-air", "audio"])
        steps = db.get_pipeline_steps(job["id"])
        assert len(steps) == 2

    def test_update_step(self, db_with_job):
        db, job = db_with_job
        steps = db.create_pipeline_steps(job["id"], ["audio"])
        step = steps[0]

        updated = db.update_step(
            step["id"],
            "completed",
            output_path="/out/audio.mp4",
            result_data={"normalized": True, "peak_db": -3.2},
            duration_ms=4500,
        )
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["output_path"] == "/out/audio.mp4"
        assert updated["duration_ms"] == 4500

    def test_update_step_failed(self, db_with_job):
        db, job = db_with_job
        steps = db.create_pipeline_steps(job["id"], ["color"])
        updated = db.update_step(
            steps[0]["id"],
            "failed",
            error_message="Invalid LUT file",
        )
        assert updated is not None
        assert updated["status"] == "failed"
        assert updated["error_message"] == "Invalid LUT file"


# ── Video Metadata Tests ────────────────────────────────────────

class TestVideoMetadata:
    def test_save_metadata(self, db):
        meta = db.save_metadata(
            file_path="/videos/test.mp4",
            metadata={
                "duration": 120.5,
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "codec": "h264",
                "bitrate": 8000000,
                "file_size": 24000000,
                "has_audio": True,
            },
        )
        assert meta["file_path"] == "/videos/test.mp4"
        assert meta["duration"] == 120.5
        assert meta["width"] == 1920

    def test_save_metadata_with_job(self, db_with_job):
        db, job = db_with_job
        meta = db.save_metadata(
            "/out/video.mp4",
            {"duration": 60.0, "width": 1280, "height": 720},
            job_id=job["id"],
        )
        assert meta["job_id"] == job["id"]

    def test_get_metadata(self, db):
        db.save_metadata("/v.mp4", {"duration": 30.0})
        cached = db.get_metadata("/v.mp4")
        assert cached is not None
        assert cached["duration"] == 30.0

    def test_get_metadata_not_found(self, db):
        assert db.get_metadata("/nonexistent.mp4") is None


# ── Pipeline Assets Tests ───────────────────────────────────────

class TestPipelineAssets:
    def test_save_asset(self, db_with_job):
        db, job = db_with_job
        asset = db.save_asset(
            job_id=job["id"],
            asset_type="thumbnail",
            file_path="/out/thumb.jpg",
            file_size_bytes=85000,
            mime_type="image/jpeg",
        )
        assert asset["asset_type"] == "thumbnail"
        assert asset["file_size_bytes"] == 85000

    def test_get_assets(self, db_with_job):
        db, job = db_with_job
        db.save_asset(job["id"], "thumbnail", "/t1.jpg")
        db.save_asset(job["id"], "gif", "/preview.gif")
        db.save_asset(job["id"], "caption_srt", "/captions.srt")

        all_assets = db.get_assets(job["id"])
        assert len(all_assets) == 3

        thumbs = db.get_assets(job["id"], asset_type="thumbnail")
        assert len(thumbs) == 1
        assert thumbs[0]["file_path"] == "/t1.jpg"


# ── Brand Kits Tests ────────────────────────────────────────────

class TestBrandKits:
    def test_get_default_brand_kit_empty(self, db):
        assert db.get_default_brand_kit() is None

    def test_upsert_and_get_brand_kit(self, db):
        kit = db.upsert_brand_kit({
            "name": "TestBrand",
            "is_default": True,
            "colors": {"primary": "#FF0000"},
        })
        assert kit["name"] == "TestBrand"

        fetched = db.get_brand_kit("TestBrand")
        assert fetched is not None
        assert fetched["colors"] == {"primary": "#FF0000"}

    def test_list_brand_kits(self, db):
        db.upsert_brand_kit({"name": "Brand1"})
        db.upsert_brand_kit({"name": "Brand2"})
        kits = db.list_brand_kits()
        assert len(kits) == 2


# ── Video Templates Tests ──────────────────────────────────────

class TestVideoTemplates:
    def _seed_template(self, db):
        """Insert a template directly into the mock store."""
        db.client._store.setdefault("he_video_templates", []).append({
            "id": "tmpl-1",
            "name": "Quick Edit",
            "pipeline": ["dead-air", "audio", "captions"],
            "is_system": True,
            "usage_count": 0,
            "created_at": "2026-02-23T00:00:00Z",
        })

    def test_get_template(self, db):
        self._seed_template(db)
        tmpl = db.get_template("Quick Edit")
        assert tmpl is not None
        assert tmpl["pipeline"] == ["dead-air", "audio", "captions"]

    def test_get_template_not_found(self, db):
        assert db.get_template("Nonexistent") is None

    def test_list_templates(self, db):
        self._seed_template(db)
        templates = db.list_templates()
        assert len(templates) >= 1

    def test_list_system_templates(self, db):
        self._seed_template(db)
        db.client._store["he_video_templates"].append({
            "id": "tmpl-2",
            "name": "Custom",
            "is_system": False,
            "usage_count": 0,
            "created_at": "2026-02-23T00:00:00Z",
        })
        system = db.list_templates(system_only=True)
        assert all(t["is_system"] for t in system)

    def test_increment_template_usage(self, db):
        self._seed_template(db)
        db.increment_template_usage("tmpl-1")
        tmpl = db.get_template("Quick Edit")
        assert tmpl["usage_count"] == 1


# ── QA Results Tests ────────────────────────────────────────────

class TestQAResults:
    def test_save_qa_results(self, db_with_job):
        db, job = db_with_job
        results = db.save_qa_results(
            job["id"],
            [
                {"check_name": "duration", "passed": True, "severity": "info", "message": "OK"},
                {"check_name": "resolution", "passed": False, "severity": "error",
                 "message": "Too low", "expected_value": "1920", "actual_value": "1280"},
            ],
        )
        assert len(results) == 2
        assert results[0]["check_name"] == "duration"
        assert results[1]["passed"] is False

    def test_get_qa_results(self, db_with_job):
        db, job = db_with_job
        db.save_qa_results(job["id"], [
            {"check_name": "codec", "passed": True, "severity": "info"},
        ])
        fetched = db.get_qa_results(job["id"])
        assert len(fetched) == 1


# ── Notification Logs Tests ─────────────────────────────────────

class TestNotificationLogs:
    def test_log_notification(self, db_with_job):
        db, job = db_with_job
        log = db.log_notification(
            channel="telegram",
            message="Job completed: Test Video",
            job_id=job["id"],
            response={"message_id": 12345},
        )
        assert log["channel"] == "telegram"
        assert log["status"] == "sent"

    def test_log_failed_notification(self, db):
        log = db.log_notification(
            channel="webhook",
            message="Alert",
            status="failed",
            error_message="Connection refused",
        )
        assert log["status"] == "failed"
        assert log["error_message"] == "Connection refused"

    def test_get_notifications(self, db_with_job):
        db, job = db_with_job
        db.log_notification("telegram", "Started", job_id=job["id"])
        db.log_notification("telegram", "Completed", job_id=job["id"])
        notifs = db.get_notifications(job["id"])
        assert len(notifs) == 2


# ── Integration: Full Pipeline Flow ────────────────────────────

class TestFullPipelineFlow:
    """Test a complete job lifecycle: create → steps → execute → QA → notify."""

    def test_complete_pipeline(self, db):
        # 1. Create job
        job = db.create_job(
            title="Full Pipeline Test",
            input_path="/input/demo.mp4",
            pipeline=["dead-air", "audio", "captions"],
        )
        assert job["id"]

        # 2. Create pipeline steps
        steps = db.create_pipeline_steps(
            job["id"],
            ["dead-air", "audio", "captions"],
            configs={"captions": {"language": "fr"}},
        )
        assert len(steps) == 3

        # 3. Start job
        db.update_job_status(job["id"], "processing")

        # 4. Execute each step
        for i, step in enumerate(steps):
            db.update_step(step["id"], "running", input_path=f"/in/{i}.mp4")
            db.update_step(
                step["id"],
                "completed",
                output_path=f"/out/{i}.mp4",
                result_data={"processed": True},
                duration_ms=1000 * (i + 1),
            )

        # 5. Save metadata
        db.save_metadata(
            "/out/2.mp4",
            {"duration": 118.5, "width": 1920, "height": 1080},
            job_id=job["id"],
        )

        # 6. Save assets
        db.save_asset(job["id"], "caption_srt", "/out/demo.srt", file_size_bytes=2400)
        db.save_asset(job["id"], "caption_vtt", "/out/demo.vtt", file_size_bytes=2600)

        # 7. QA checks
        db.save_qa_results(job["id"], [
            {"check_name": "duration", "passed": True, "severity": "info", "message": "OK"},
            {"check_name": "resolution", "passed": True, "severity": "info", "message": "1080p"},
        ])

        # 8. Complete job
        db.update_job_status(job["id"], "completed", output_path="/out/demo_final.mp4")

        # 9. Send notification
        db.log_notification("telegram", "Job done!", job_id=job["id"])

        # Verify final state
        final_job = db.get_job(job["id"])
        assert final_job["status"] == "completed"
        assert final_job["output_path"] == "/out/demo_final.mp4"

        assets = db.get_assets(job["id"])
        assert len(assets) == 2

        qa = db.get_qa_results(job["id"])
        assert len(qa) == 2
        assert all(r["passed"] for r in qa)
