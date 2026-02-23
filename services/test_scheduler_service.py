import pytest
import json
from pathlib import Path
from scheduler_service import SchedulerService, JobStatus


@pytest.fixture
def scheduler(tmp_path):
    return SchedulerService(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        state_file=tmp_path / "state.json",
    )


@pytest.fixture
def scheduler_with_videos(scheduler, tmp_path):
    """Scheduler with fake video files in input dir."""
    input_dir = tmp_path / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in ["video1.mp4", "video2.mov", "notes.txt"]:
        (input_dir / name).touch()
    return scheduler


def test_create_job(scheduler, tmp_path):
    job = scheduler.create_job(
        input_path=Path("test.mp4"),
        skills=["dead_air", "captions"],
    )
    assert job.id == "job_0001"
    assert job.status == JobStatus.QUEUED
    assert "dead_air" in job.skills


def test_scan_for_new_files(scheduler_with_videos):
    new_jobs = scheduler_with_videos.scan_for_new_files()
    # Should find 2 video files, ignore .txt
    assert len(new_jobs) == 2
    names = [Path(j.input_path).name for j in new_jobs]
    assert "video1.mp4" in names
    assert "video2.mov" in names
    assert "notes.txt" not in names


def test_scan_skips_already_processed(scheduler_with_videos):
    first_scan = scheduler_with_videos.scan_for_new_files()
    assert len(first_scan) == 2
    second_scan = scheduler_with_videos.scan_for_new_files()
    assert len(second_scan) == 0


def test_job_lifecycle(scheduler):
    job = scheduler.create_job(Path("test.mp4"), ["dead_air"])
    assert job.status == JobStatus.QUEUED

    scheduler.start_job(job.id)
    assert job.status == JobStatus.PROCESSING
    assert job.started_at is not None

    scheduler.complete_job(job.id, {"output": "done.mp4"})
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"output": "done.mp4"}


def test_fail_job(scheduler):
    job = scheduler.create_job(Path("test.mp4"), ["dead_air"])
    scheduler.start_job(job.id)
    scheduler.fail_job(job.id, "FFmpeg crashed")
    assert job.status == JobStatus.FAILED
    assert job.error == "FFmpeg crashed"


def test_cancel_job(scheduler):
    job = scheduler.create_job(Path("test.mp4"), ["dead_air"])
    scheduler.cancel_job(job.id)
    assert job.status == JobStatus.CANCELLED


def test_priority_ordering(scheduler):
    low = scheduler.create_job(Path("low.mp4"), priority=0)
    high = scheduler.create_job(Path("high.mp4"), priority=10)
    medium = scheduler.create_job(Path("med.mp4"), priority=5)

    next_job = scheduler.get_next_job()
    assert next_job.id == high.id


def test_queue_status(scheduler):
    scheduler.create_job(Path("a.mp4"))
    scheduler.create_job(Path("b.mp4"))
    job_c = scheduler.create_job(Path("c.mp4"))
    scheduler.start_job(job_c.id)
    scheduler.complete_job(job_c.id, {})

    status = scheduler.get_queue_status()
    assert status["total_jobs"] == 3
    assert status["by_status"]["queued"] == 2
    assert status["by_status"]["completed"] == 1


def test_state_persistence(tmp_path):
    state_file = tmp_path / "state.json"

    # Create scheduler with jobs
    s1 = SchedulerService(
        input_dir=tmp_path / "in",
        output_dir=tmp_path / "out",
        state_file=state_file,
    )
    s1.create_job(Path("video.mp4"), ["dead_air"])
    s1.create_job(Path("video2.mp4"), ["captions"])
    assert state_file.exists()

    # Load state in new scheduler
    s2 = SchedulerService(
        input_dir=tmp_path / "in",
        output_dir=tmp_path / "out",
        state_file=state_file,
    )
    assert len(s2._queue) == 2
    assert len(s2._processed_files) == 2


def test_process_next_with_handler(scheduler):
    scheduler.create_job(Path("test.mp4"), ["dead_air"])
    scheduler.set_job_handler(lambda job: {"processed": True})

    result = scheduler.process_next()
    assert result["status"] == "completed"
    assert result["result"]["processed"] is True


def test_process_next_no_handler(scheduler):
    scheduler.create_job(Path("test.mp4"))
    with pytest.raises(RuntimeError, match="No job handler"):
        scheduler.process_next()


def test_process_next_empty_queue(scheduler):
    scheduler.set_job_handler(lambda job: {})
    result = scheduler.process_next()
    assert result is None
