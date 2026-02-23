"""Skill 14: Thumbnail Generation.

Generate video thumbnails by extracting frames at key moments,
scaling to a target resolution, and selecting the best candidate.
Uses FFmpeg for frame extraction and scaling.
"""

import argparse
import subprocess
from pathlib import Path

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class ThumbnailGenerator:
    """Extract and scale video frames as thumbnail images."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_dir: Path,
        count: int = 3,
        format: str = "jpg",
        width: int = 1280,
        height: int = 720,
    ) -> dict:
        """Full V-I-V cycle for thumbnail generation.

        Args:
            input_path: Source video file.
            output_dir: Directory where thumbnails will be saved.
            count: Number of thumbnails to extract.
            format: Image format (jpg or png).
            width: Target width in pixels.
            height: Target height in pixels.

        Returns:
            dict with thumbnails list, count, format, and best_thumbnail.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        # get_metadata raises ValueError if no video stream found

        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        # === IMPLEMENT ===
        duration = meta.duration
        timestamps = self._calculate_timestamps(duration, count)

        thumbnails = []
        for i, ts in enumerate(timestamps):
            filename = f"thumb_{i:03d}.{format}"
            output_path = output_dir / filename
            thumb_info = self._extract_and_scale(
                input_path, output_path, ts, width, height
            )
            thumbnails.append(thumb_info)

        # === VERIFY (After) ===
        valid_thumbnails = []
        for thumb in thumbnails:
            path = Path(thumb["path"])
            if not path.exists():
                raise RuntimeError(f"Thumbnail was not created: {path}")
            if thumb["size_bytes"] < 1024:
                raise RuntimeError(
                    f"Thumbnail too small ({thumb['size_bytes']} bytes), "
                    f"likely corrupt: {path}"
                )
            valid_thumbnails.append(thumb)

        best = self._get_best_thumbnail(valid_thumbnails)

        return {
            "thumbnails": valid_thumbnails,
            "count": len(valid_thumbnails),
            "format": format,
            "best_thumbnail": best,
        }

    def extract_at_timestamps(
        self,
        input_path: Path,
        output_dir: Path,
        timestamps: list[float],
        format: str = "jpg",
        width: int = 1280,
        height: int = 720,
    ) -> list[dict]:
        """Extract frames at specific timestamps.

        Args:
            input_path: Source video file.
            output_dir: Directory where thumbnails will be saved.
            timestamps: List of timestamps in seconds.
            format: Image format (jpg or png).
            width: Target width in pixels.
            height: Target height in pixels.

        Returns:
            List of dicts with path, timestamp, and size_bytes for each thumbnail.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        self.ffmpeg.get_metadata(input_path)  # validates video stream exists

        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        thumbnails = []
        for i, ts in enumerate(timestamps):
            filename = f"thumb_{i:03d}.{format}"
            output_path = output_dir / filename
            thumb_info = self._extract_and_scale(
                input_path, output_path, ts, width, height
            )
            thumbnails.append(thumb_info)

        return thumbnails

    def _calculate_timestamps(self, duration: float, count: int) -> list[float]:
        """Distribute timestamps evenly, skipping first and last 5%.

        For very short videos (< 2s), uses the full duration range instead.

        Args:
            duration: Video duration in seconds.
            count: Number of timestamps to generate.

        Returns:
            List of timestamps in seconds.
        """
        if count <= 0:
            return []

        if count == 1:
            return [duration / 2.0]

        # For very short videos, use the full range
        if duration < 2.0:
            margin = 0.0
        else:
            margin = duration * 0.05  # skip first/last 5%

        start = margin
        end = duration - margin

        if count == 1:
            return [(start + end) / 2.0]

        step = (end - start) / (count - 1)
        return [start + i * step for i in range(count)]

    def _extract_and_scale(
        self,
        input_path: Path,
        output_path: Path,
        timestamp: float,
        width: int,
        height: int,
    ) -> dict:
        """Extract a single frame at timestamp and scale to target resolution.

        Args:
            input_path: Source video file.
            output_path: Destination image file.
            timestamp: Time position in seconds.
            width: Target width.
            height: Target height.

        Returns:
            dict with path, timestamp, and size_bytes.
        """
        cmd = [
            self.ffmpeg.ffmpeg,
            "-ss", str(timestamp),
            "-i", str(input_path),
            "-frames:v", "1",
            "-vf", f"scale={width}:{height}",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        size_bytes = output_path.stat().st_size if output_path.exists() else 0

        return {
            "path": str(output_path),
            "timestamp": timestamp,
            "size_bytes": size_bytes,
        }

    def _get_best_thumbnail(self, thumbnails: list[dict]) -> dict:
        """Pick the best thumbnail by largest file size.

        Heuristic: more visual detail produces a larger compressed file.

        Args:
            thumbnails: List of thumbnail info dicts.

        Returns:
            The thumbnail dict with the largest size_bytes.
        """
        if not thumbnails:
            return {}
        return max(thumbnails, key=lambda t: t["size_bytes"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate thumbnails from a video"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for thumbnails"
    )
    parser.add_argument(
        "--count", type=int, default=3, help="Number of thumbnails (default 3)"
    )
    parser.add_argument(
        "--format", default="jpg", choices=["jpg", "png"],
        help="Image format (default jpg)"
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Target width (default 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Target height (default 720)"
    )
    parser.add_argument(
        "--timestamps", type=float, nargs="+", default=None,
        help="Specific timestamps in seconds (overrides --count)"
    )

    args = parser.parse_args()

    gen = ThumbnailGenerator()

    if args.timestamps:
        thumbs = gen.extract_at_timestamps(
            input_path=Path(args.input),
            output_dir=Path(args.output_dir),
            timestamps=args.timestamps,
            format=args.format,
            width=args.width,
            height=args.height,
        )
        print(f"\n=== Extracted {len(thumbs)} Thumbnails ===")
        for t in thumbs:
            print(f"  {t['timestamp']:.1f}s -> {t['path']} ({t['size_bytes']} bytes)")
    else:
        result = gen.execute(
            input_path=Path(args.input),
            output_dir=Path(args.output_dir),
            count=args.count,
            format=args.format,
            width=args.width,
            height=args.height,
        )
        print(f"\n=== Thumbnail Generation Complete ===")
        print(f"Count: {result['count']}")
        print(f"Format: {result['format']}")
        for t in result["thumbnails"]:
            print(f"  {t['timestamp']:.1f}s -> {t['path']} ({t['size_bytes']} bytes)")
        if result.get("best_thumbnail"):
            best = result["best_thumbnail"]
            print(f"Best: {best['path']} ({best['size_bytes']} bytes)")
