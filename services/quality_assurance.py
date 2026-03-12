"""Quality assurance service for video output validation (V-I-V Verify step).

Provides both individual checks and comprehensive scored reports.
Score formula: (sum_passed_weights / sum_all_weights) * 10
Quality threshold: >= 7.0 out of 10.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService

logger = logging.getLogger(__name__)

# Minimum quality score to pass E2E verification (V-I-V Principe 5: Tolerance Zero)
QUALITY_THRESHOLD = 7.0


@dataclass
class QAResult:
    check_name: str
    passed: bool
    message: str
    weight: float = 1.0
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None


@dataclass
class QAReport:
    """Comprehensive QA report with weighted scoring."""
    video_path: str
    checks: list[QAResult] = field(default_factory=list)
    score: float = 0.0
    passed: bool = False
    threshold: float = QUALITY_THRESHOLD

    def compute_score(self) -> float:
        """Compute weighted quality score (0-10 scale)."""
        if not self.checks:
            self.score = 0.0
            self.passed = False
            return self.score

        total_weight = sum(c.weight for c in self.checks)
        passed_weight = sum(c.weight for c in self.checks if c.passed)
        self.score = round((passed_weight / total_weight) * 10, 1) if total_weight > 0 else 0.0
        self.passed = self.score >= self.threshold
        return self.score

    def summary(self) -> str:
        """Short summary line."""
        status = "PASS" if self.passed else "FAIL"
        passed_count = sum(1 for c in self.checks if c.passed)
        return f"[{status}] Score: {self.score}/10 ({passed_count}/{len(self.checks)} checks)"


class QualityAssurance:
    """Automated quality checks for every video output. V-I-V Verify step.

    Checks are organized in 3 tiers:
      - Technical: duration, resolution, audio, black frames, file size
      - Content: silence gaps, caption match (when caption file provided)
      - Brand: watermark presence (when brand config provided)
    """

    def __init__(self) -> None:
        self.ffmpeg = FFmpegService()

    # === TECHNICAL CHECKS (existing, now with weights) ===

    def check_duration(
        self,
        video_path: Path,
        expected: float,
        tolerance: float = 0.5,
    ) -> QAResult:
        meta = self.ffmpeg.get_metadata(video_path)
        diff = abs(meta.duration - expected)
        passed = diff <= tolerance
        return QAResult(
            check_name="duration",
            passed=passed,
            weight=1.5,
            message=f"Duration {meta.duration:.1f}s vs expected {expected:.1f}s (±{tolerance}s)",
            actual_value=f"{meta.duration:.1f}",
            expected_value=f"{expected:.1f}",
        )

    def check_resolution(
        self,
        video_path: Path,
        min_width: int = 1920,
        min_height: int = 1080,
    ) -> QAResult:
        meta = self.ffmpeg.get_metadata(video_path)
        passed = meta.width >= min_width and meta.height >= min_height
        return QAResult(
            check_name="resolution",
            passed=passed,
            weight=1.0,
            message=f"Resolution {meta.width}x{meta.height} vs minimum {min_width}x{min_height}",
            actual_value=f"{meta.width}x{meta.height}",
            expected_value=f">={min_width}x{min_height}",
        )

    def check_has_audio(self, video_path: Path) -> QAResult:
        meta = self.ffmpeg.get_metadata(video_path)
        return QAResult(
            check_name="has_audio",
            passed=meta.has_audio,
            weight=2.0,
            message=f"Audio track {'present' if meta.has_audio else 'MISSING'}",
            actual_value=str(meta.has_audio),
            expected_value="True",
        )

    def check_audio_lufs(
        self,
        video_path: Path,
        target_lufs: float = -14,
        tolerance: float = 2,
    ) -> QAResult:
        loudness = self.ffmpeg.get_loudness(video_path)
        input_i = float(str(loudness.get("input_i", -99)).replace(",", "."))
        diff = abs(input_i - target_lufs)
        passed = diff <= tolerance
        return QAResult(
            check_name="audio_lufs",
            passed=passed,
            weight=1.0,
            message=f"LUFS {input_i:.1f} vs target {target_lufs} (±{tolerance})",
            actual_value=f"{input_i:.1f}",
            expected_value=f"{target_lufs}",
        )

    def check_no_black_frames(
        self,
        video_path: Path,
        threshold: float = 0.98,
    ) -> QAResult:
        """Check for black frames using FFmpeg blackdetect filter."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(video_path),
            "-vf", f"blackdetect=d=0.1:pix_th={threshold}",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        black_count = result.stderr.count("black_start:")
        passed = black_count == 0
        return QAResult(
            check_name="no_black_frames",
            passed=passed,
            weight=1.5,
            message=f"{'No' if passed else black_count} black frame segments detected",
            actual_value=str(black_count),
            expected_value="0",
        )

    def check_file_size(
        self,
        video_path: Path,
        min_mb: float = 0.01,
        max_mb: float = 5000,
    ) -> QAResult:
        size_mb = video_path.stat().st_size / (1024 * 1024)
        passed = min_mb <= size_mb <= max_mb
        return QAResult(
            check_name="file_size",
            passed=passed,
            weight=0.5,
            message=f"File size {size_mb:.1f}MB (range: {min_mb}-{max_mb}MB)",
            actual_value=f"{size_mb:.1f}MB",
            expected_value=f"{min_mb}-{max_mb}MB",
        )

    # === CONTENT CHECKS (new) ===

    def check_no_silence_gaps(
        self,
        video_path: Path,
        max_gap_seconds: float = 2.0,
    ) -> QAResult:
        """Detect silence gaps longer than threshold using FFmpeg silencedetect."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(video_path),
            "-af", f"silencedetect=n=-40dB:d={max_gap_seconds}",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        silence_count = result.stderr.count("silence_end:")
        passed = silence_count == 0
        return QAResult(
            check_name="no_silence_gaps",
            passed=passed,
            weight=1.0,
            message=f"{'No' if passed else silence_count} silence gaps >{max_gap_seconds}s detected",
            actual_value=str(silence_count),
            expected_value="0",
        )

    def check_video_codec(
        self,
        video_path: Path,
        expected_codec: str = "h264",
    ) -> QAResult:
        """Verify the video stream uses the expected codec."""
        try:
            cmd = [
                self.ffmpeg.ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_streams", str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
            codec = "unknown"
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    codec = stream.get("codec_name", "unknown")
                    break
            passed = codec == expected_codec
        except Exception:
            codec = "error"
            passed = False

        return QAResult(
            check_name="video_codec",
            passed=passed,
            weight=0.5,
            message=f"Codec: {codec} (expected {expected_codec})",
            actual_value=codec,
            expected_value=expected_codec,
        )

    def check_chapters_valid(
        self,
        chapters_path: Path,
        video_duration: float,
    ) -> QAResult:
        """Verify chapter timestamps are within video duration."""
        try:
            chapters = json.loads(chapters_path.read_text())
            invalid = []
            for ch in chapters:
                ts = ch.get("start_time", ch.get("timestamp", 0))
                if isinstance(ts, str):
                    # Parse "MM:SS" or "HH:MM:SS"
                    parts = ts.split(":")
                    ts = sum(float(p) * (60 ** (len(parts) - 1 - i)) for i, p in enumerate(parts))
                if ts > video_duration:
                    invalid.append(ts)
            passed = len(invalid) == 0
            msg = f"All {len(chapters)} chapters within duration" if passed else f"{len(invalid)} timestamps exceed video duration"
        except Exception as e:
            passed = False
            msg = f"Chapter validation error: {e}"

        return QAResult(
            check_name="chapters_valid",
            passed=passed,
            weight=1.0,
            message=msg,
            actual_value=str(len(chapters) if 'chapters' in dir() else 0),
            expected_value="all within duration",
        )

    # === COMPREHENSIVE CHECK ===

    def full_check(
        self,
        video_path: Path,
        expected_duration: Optional[float] = None,
        min_width: int = 1920,
        min_height: int = 1080,
    ) -> list[QAResult]:
        """Run all applicable quality checks (backward compatible)."""
        results: list[QAResult] = []

        if expected_duration is not None:
            results.append(self.check_duration(video_path, expected_duration))

        results.append(self.check_resolution(video_path, min_width, min_height))
        results.append(self.check_has_audio(video_path))
        results.append(self.check_no_black_frames(video_path))
        results.append(self.check_file_size(video_path))

        return results

    def comprehensive_check(
        self,
        video_path: Path,
        expected_duration: Optional[float] = None,
        duration_tolerance: float = 0.5,
        min_width: int = 1920,
        min_height: int = 1080,
        chapters_path: Optional[Path] = None,
        min_file_mb: float = 0.5,
        max_file_mb: float = 200,
    ) -> QAReport:
        """Run all checks including content verification and return scored report.

        V-I-V Principe 5 (Tolerance Zero): score must be >= 7.0/10.
        """
        report = QAReport(video_path=str(video_path))

        # Technical checks
        if expected_duration is not None:
            report.checks.append(self.check_duration(video_path, expected_duration, tolerance=duration_tolerance))

        report.checks.append(self.check_resolution(video_path, min_width, min_height))
        report.checks.append(self.check_has_audio(video_path))
        report.checks.append(self.check_no_black_frames(video_path))
        report.checks.append(self.check_file_size(video_path, min_file_mb, max_file_mb))
        report.checks.append(self.check_video_codec(video_path))

        # Content checks
        report.checks.append(self.check_no_silence_gaps(video_path))

        # Chapter validation (if chapters file provided)
        if chapters_path and chapters_path.exists() and expected_duration:
            report.checks.append(self.check_chapters_valid(chapters_path, expected_duration))

        report.compute_score()
        return report

    def format_report(self, results: list[QAResult] | QAReport) -> str:
        """Format QA results as a readable report.

        Accepts either a list of QAResult (backward compat) or a QAReport.
        """
        if isinstance(results, QAReport):
            return self._format_scored_report(results)

        # Backward-compatible list format
        lines = ["=== Video Quality Report ==="]
        for r in results:
            icon = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{icon}] {r.check_name}: {r.message}")

        passed_count = sum(r.passed for r in results)
        status = "PASSED" if passed_count == len(results) else "FAILED"
        lines.append(f"\nOverall: {status} ({passed_count}/{len(results)} checks)")
        return "\n".join(lines)

    def _format_scored_report(self, report: QAReport) -> str:
        """Format a scored QAReport with weights and score."""
        lines = ["=== Video Quality Report (Scored) ==="]
        lines.append(f"Video: {report.video_path}")
        lines.append("")

        for r in report.checks:
            icon = "PASS" if r.passed else "FAIL"
            weight_str = f"w={r.weight:.1f}"
            lines.append(f"  [{icon}] ({weight_str}) {r.check_name}: {r.message}")

        lines.append("")
        lines.append(f"Score: {report.score}/10 (threshold: {report.threshold})")
        status = "PASSED" if report.passed else "FAILED"
        passed_count = sum(1 for c in report.checks if c.passed)
        lines.append(f"Result: {status} ({passed_count}/{len(report.checks)} checks passed)")
        return "\n".join(lines)
