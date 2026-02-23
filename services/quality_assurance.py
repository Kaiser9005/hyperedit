"""Quality assurance service for video output validation (V-I-V Verify step)."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService


@dataclass
class QAResult:
    check_name: str
    passed: bool
    message: str
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None


class QualityAssurance:
    """Automated quality checks for every video output. V-I-V Verify step."""

    def __init__(self):
        self.ffmpeg = FFmpegService()

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
            message=f"Resolution {meta.width}x{meta.height} vs minimum {min_width}x{min_height}",
            actual_value=f"{meta.width}x{meta.height}",
            expected_value=f">={min_width}x{min_height}",
        )

    def check_has_audio(self, video_path: Path) -> QAResult:
        meta = self.ffmpeg.get_metadata(video_path)
        return QAResult(
            check_name="has_audio",
            passed=meta.has_audio,
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
        result = subprocess.run(cmd, capture_output=True, text=True)
        black_count = result.stderr.count("black_start:")
        passed = black_count == 0
        return QAResult(
            check_name="no_black_frames",
            passed=passed,
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
            message=f"File size {size_mb:.1f}MB (range: {min_mb}-{max_mb}MB)",
            actual_value=f"{size_mb:.1f}MB",
            expected_value=f"{min_mb}-{max_mb}MB",
        )

    def full_check(
        self,
        video_path: Path,
        expected_duration: Optional[float] = None,
        min_width: int = 1920,
        min_height: int = 1080,
    ) -> list[QAResult]:
        """Run all applicable quality checks."""
        results = []

        if expected_duration is not None:
            results.append(self.check_duration(video_path, expected_duration))

        results.append(self.check_resolution(video_path, min_width, min_height))
        results.append(self.check_has_audio(video_path))
        results.append(self.check_no_black_frames(video_path))
        results.append(self.check_file_size(video_path))

        return results

    def format_report(self, results: list[QAResult]) -> str:
        """Format QA results as a readable report."""
        lines = ["=== Video Quality Report ==="]
        all_passed = True
        for r in results:
            icon = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{icon}] {r.check_name}: {r.message}")
            if not r.passed:
                all_passed = False

        status = "PASSED" if all_passed else "FAILED"
        lines.append(f"\nOverall: {status} ({sum(r.passed for r in results)}/{len(results)} checks)")
        return "\n".join(lines)
