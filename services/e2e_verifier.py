"""E2E Verification Service — automated quality gate for the video pipeline.

Integrates with QualityAssurance scoring system and Supabase persistence.
V-I-V Cycle: verifies every pipeline output meets quality threshold (>= 7.0/10).

Usage:
    verifier = E2EVerifier()
    report = verifier.verify_pipeline_output(job_id, output_path, config)
    if not report.passed:
        report = verifier.verify_with_retry(job_id, output_path, config)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quality_assurance import QAReport, QualityAssurance, QUALITY_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class VerificationConfig:
    """Configuration for E2E verification checks."""
    expected_duration: Optional[float] = None
    duration_tolerance: float = 0.5
    min_width: int = 1920
    min_height: int = 1080
    min_file_mb: float = 0.5
    max_file_mb: float = 200
    chapters_path: Optional[Path] = None
    persist_to_db: bool = True


class E2EVerifier:
    """End-to-end verification service for video pipeline outputs.

    Runs comprehensive QA checks, persists results to Supabase,
    and supports retry with re-generation on failure.
    """

    def __init__(self) -> None:
        self.qa = QualityAssurance()
        self._db = None  # Lazy-loaded to avoid circular imports

    def verify_pipeline_output(
        self,
        job_id: str,
        output_path: Path,
        config: Optional[VerificationConfig] = None,
    ) -> QAReport:
        """Run comprehensive verification on a pipeline output.

        Args:
            job_id: Pipeline job identifier (for DB persistence).
            output_path: Path to the final video file.
            config: Verification configuration (defaults applied if None).

        Returns:
            QAReport with score and pass/fail status.
        """
        config = config or VerificationConfig()
        output_path = Path(output_path)

        if not output_path.exists():
            report = QAReport(video_path=str(output_path))
            report.score = 0.0
            report.passed = False
            logger.error("V-I-V FAIL: Output file does not exist: %s", output_path)
            return report

        logger.info("E2E verification starting for job %s: %s", job_id, output_path.name)

        report = self.qa.comprehensive_check(
            video_path=output_path,
            expected_duration=config.expected_duration,
            duration_tolerance=config.duration_tolerance,
            min_width=config.min_width,
            min_height=config.min_height,
            chapters_path=config.chapters_path,
            min_file_mb=config.min_file_mb,
            max_file_mb=config.max_file_mb,
        )

        # Log detailed report
        logger.info(
            "E2E verification for job %s: score=%.1f/10 (%s)",
            job_id, report.score, "PASS" if report.passed else "FAIL",
        )
        for check in report.checks:
            level = logging.INFO if check.passed else logging.WARNING
            logger.log(level, "  [%s] %s: %s", "OK" if check.passed else "FAIL", check.check_name, check.message)

        # Persist to Supabase
        if config.persist_to_db:
            self._persist_result(job_id, report)

        return report

    def verify_with_retry(
        self,
        job_id: str,
        output_path: Path,
        config: Optional[VerificationConfig] = None,
        max_retries: int = 2,
    ) -> QAReport:
        """Verify with retry — re-checks after each attempt.

        Does NOT re-generate the video (that's the pipeline's job).
        Retries verification in case of transient failures (ffprobe timeout, etc.).

        Args:
            job_id: Pipeline job identifier.
            output_path: Path to the final video file.
            config: Verification configuration.
            max_retries: Maximum number of retry attempts.

        Returns:
            QAReport from the last verification attempt.
        """
        for attempt in range(1, max_retries + 2):  # 1 initial + max_retries
            report = self.verify_pipeline_output(job_id, output_path, config)

            if report.passed:
                logger.info(
                    "E2E verification PASSED on attempt %d: score=%.1f/10",
                    attempt, report.score,
                )
                return report

            if attempt <= max_retries:
                logger.warning(
                    "E2E verification attempt %d FAILED (score=%.1f/10). Retrying...",
                    attempt, report.score,
                )
                time.sleep(1)  # Brief pause before retry

        logger.error(
            "E2E verification FAILED after %d attempts: score=%.1f/10",
            max_retries + 1, report.score,
        )
        return report

    def _persist_result(self, job_id: str, report: QAReport) -> None:
        """Persist verification result to Supabase he_qa_results table."""
        try:
            if self._db is None:
                from database_service import DatabaseService
                self._db = DatabaseService()

            check_rows = [
                {
                    "check_name": c.check_name,
                    "passed": c.passed,
                    "severity": "error" if not c.passed and c.weight >= 1.5 else "warning" if not c.passed else "info",
                    "message": f"[w={c.weight}] {c.message} (score: {report.score}/10)",
                    "expected_value": c.expected_value,
                    "actual_value": c.actual_value,
                }
                for c in report.checks
            ]

            self._db.save_qa_results(
                job_id=job_id,
                results=check_rows,
            )
            logger.info("QA result persisted to Supabase for job %s", job_id)
        except Exception as e:
            logger.warning("Failed to persist QA result: %s", e)
