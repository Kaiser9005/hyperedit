"""Skill 7: GIF Integration.

Extract GIFs from video segments or convert full videos to GIF.
Uses two-pass FFmpeg palette generation for high-quality output.
"""

import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


GIF_PRESETS = {
    "high": {"width": 640, "fps": 24, "max_colors": 256},
    "medium": {"width": 480, "fps": 15, "max_colors": 128},
    "low": {"width": 320, "fps": 10, "max_colors": 64},
    "thumbnail": {"width": 200, "fps": 8, "max_colors": 32},
}


class GifManager:
    """Extract, convert, and optimize GIFs from video files."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def extract_gif(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
        width: int = 480,
        fps: int = 15,
        max_colors: int = 256,
    ) -> dict:
        """Extract a video segment as a GIF using two-pass palette method.

        V-I-V cycle:
          VERIFY  - input exists, start < end
          IMPLEMENT - palettegen pass then paletteuse pass
          VERIFY  - output exists and is a valid GIF

        Args:
            input_path: Source video file.
            output_path: Destination GIF file.
            start: Segment start time in seconds.
            end: Segment end time in seconds.
            width: Output width in pixels (height auto-scaled).
            fps: Frames per second in the GIF.
            max_colors: Maximum palette colors (2-256).

        Returns:
            dict with output_path, duration, width, file_size_bytes, fps.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")
        if start >= end:
            raise ValueError(
                f"start ({start}) must be less than end ({end})"
            )

        # === IMPLEMENT ===
        with tempfile.TemporaryDirectory() as tmp_dir:
            palette_path = Path(tmp_dir) / "palette.png"

            self._generate_palette(
                input_path, palette_path, start, end, width, fps, max_colors
            )
            self._apply_palette(
                input_path, palette_path, output_path, start, end, width, fps
            )

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"GIF output was not created: {output_path}")

        self._validate_gif(output_path)

        duration = end - start
        file_size = output_path.stat().st_size

        return {
            "output_path": str(output_path),
            "duration": round(duration, 2),
            "width": width,
            "file_size_bytes": file_size,
            "fps": fps,
        }

    def video_to_gif(
        self,
        input_path: Path,
        output_path: Path,
        width: int = 480,
        fps: int = 15,
        max_duration: float = 10,
    ) -> dict:
        """Convert a full video (or first max_duration seconds) to GIF.

        Args:
            input_path: Source video file.
            output_path: Destination GIF file.
            width: Output width in pixels.
            fps: Frames per second.
            max_duration: Maximum seconds to convert (default 10).

        Returns:
            dict with output_path, duration, width, file_size_bytes, fps.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        duration = min(meta.duration, max_duration)

        return self.extract_gif(
            input_path=input_path,
            output_path=output_path,
            start=0,
            end=duration,
            width=width,
            fps=fps,
        )

    def optimize_gif(
        self,
        input_path: Path,
        output_path: Path,
        max_size_kb: int = 5000,
    ) -> dict:
        """Reduce GIF size by iteratively lowering fps, width, and colors.

        Args:
            input_path: Source GIF or video file.
            output_path: Destination for optimized GIF.
            max_size_kb: Target maximum file size in kilobytes.

        Returns:
            dict with original_size, optimized_size, reductions_applied.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        original_size = input_path.stat().st_size
        max_size_bytes = max_size_kb * 1024

        # Get video duration from the input
        meta = self.ffmpeg.get_metadata(input_path)
        duration = meta.duration

        # Reduction steps: progressively degrade quality
        reduction_steps = [
            {"width": 480, "fps": 15, "max_colors": 256},
            {"width": 480, "fps": 12, "max_colors": 128},
            {"width": 400, "fps": 10, "max_colors": 128},
            {"width": 320, "fps": 10, "max_colors": 64},
            {"width": 320, "fps": 8, "max_colors": 64},
            {"width": 240, "fps": 8, "max_colors": 32},
            {"width": 200, "fps": 6, "max_colors": 32},
        ]

        reductions_applied = []

        # If already under target, just copy
        if original_size <= max_size_bytes:
            import shutil
            shutil.copy2(input_path, output_path)
            return {
                "original_size": original_size,
                "optimized_size": original_size,
                "reductions_applied": ["none_needed"],
            }

        for step in reduction_steps:
            with tempfile.TemporaryDirectory() as tmp_dir:
                palette_path = Path(tmp_dir) / "palette.png"

                self._generate_palette(
                    input_path, palette_path,
                    start=0, end=duration,
                    width=step["width"],
                    fps=step["fps"],
                    max_colors=step["max_colors"],
                )
                self._apply_palette(
                    input_path, palette_path, output_path,
                    start=0, end=duration,
                    width=step["width"],
                    fps=step["fps"],
                )

            current_size = output_path.stat().st_size
            reductions_applied.append(
                f"w={step['width']},fps={step['fps']},colors={step['max_colors']}"
                f" -> {current_size // 1024}KB"
            )

            if current_size <= max_size_bytes:
                break

        optimized_size = output_path.stat().st_size

        return {
            "original_size": original_size,
            "optimized_size": optimized_size,
            "reductions_applied": reductions_applied,
        }

    def list_presets(self) -> dict:
        """Return available GIF quality presets."""
        return dict(GIF_PRESETS)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_palette(
        self,
        input_path: Path,
        palette_path: Path,
        start: float,
        end: float,
        width: int,
        fps: int,
        max_colors: int,
    ) -> Path:
        """FFmpeg palettegen pass: create an optimal color palette.

        Args:
            input_path: Source video file.
            palette_path: Destination for the palette PNG.
            start: Segment start time.
            end: Segment end time.
            width: Scale width (-1 preserves aspect ratio).
            fps: Target frame rate.
            max_colors: Maximum colors in palette (2-256).

        Returns:
            Path to the generated palette file.
        """
        filters = f"fps={fps},scale={width}:-1:flags=lanczos,palettegen=max_colors={max_colors}"
        cmd = [
            self.ffmpeg.ffmpeg,
            "-ss", str(start),
            "-t", str(end - start),
            "-i", str(input_path),
            "-vf", filters,
            str(palette_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return palette_path

    def _apply_palette(
        self,
        input_path: Path,
        palette_path: Path,
        output_path: Path,
        start: float,
        end: float,
        width: int,
        fps: int,
    ) -> Path:
        """FFmpeg paletteuse pass: render GIF with the generated palette.

        Args:
            input_path: Source video file.
            palette_path: Palette PNG from _generate_palette.
            output_path: Destination GIF file.
            start: Segment start time.
            end: Segment end time.
            width: Scale width (-1 preserves aspect ratio).
            fps: Target frame rate.

        Returns:
            Path to the created GIF.
        """
        filter_complex = (
            f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse"
        )
        cmd = [
            self.ffmpeg.ffmpeg,
            "-ss", str(start),
            "-t", str(end - start),
            "-i", str(input_path),
            "-i", str(palette_path),
            "-filter_complex", filter_complex,
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _validate_gif(self, gif_path: Path) -> None:
        """Verify file is a valid GIF by checking magic bytes."""
        with open(gif_path, "rb") as f:
            header = f.read(6)
        if header[:3] != b"GIF":
            raise RuntimeError(
                f"Output is not a valid GIF file: {gif_path}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GIF extraction and optimization")
    parser.add_argument("--input", required=True, help="Input video/GIF path")
    parser.add_argument("--output", required=True, help="Output GIF path")
    parser.add_argument(
        "--mode",
        choices=["extract", "video-to-gif", "optimize"],
        default="extract",
        help="Operation mode",
    )
    parser.add_argument("--start", type=float, default=0, help="Start time (seconds)")
    parser.add_argument("--end", type=float, default=2, help="End time (seconds)")
    parser.add_argument("--width", type=int, default=480, help="Output width")
    parser.add_argument("--fps", type=int, default=15, help="Frames per second")
    parser.add_argument("--max-colors", type=int, default=256, help="Max palette colors")
    parser.add_argument("--max-duration", type=float, default=10, help="Max duration for video-to-gif")
    parser.add_argument("--max-size", type=int, default=5000, help="Max size in KB for optimize mode")

    args = parser.parse_args()

    manager = GifManager()

    if args.mode == "extract":
        result = manager.extract_gif(
            input_path=Path(args.input),
            output_path=Path(args.output),
            start=args.start,
            end=args.end,
            width=args.width,
            fps=args.fps,
            max_colors=args.max_colors,
        )
    elif args.mode == "video-to-gif":
        result = manager.video_to_gif(
            input_path=Path(args.input),
            output_path=Path(args.output),
            width=args.width,
            fps=args.fps,
            max_duration=args.max_duration,
        )
    elif args.mode == "optimize":
        result = manager.optimize_gif(
            input_path=Path(args.input),
            output_path=Path(args.output),
            max_size_kb=args.max_size,
        )

    print("\n=== GIF Operation Complete ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
