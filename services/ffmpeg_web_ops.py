"""FFmpeg Web Operations — frame extraction, web optimization, and poster generation.

Extends FFmpegService with operations specific to web/marketing production:
- WebP frame extraction for scroll-driven animations
- VP9/WebM encoding for modern browsers
- Poster and thumbnail generation
- GIF creation for ad previews
- Sprite sheet generation for seek bars

All commands follow the exact specifications from the SKILL.md reference.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService

logger = logging.getLogger(__name__)


class FFmpegWebOps:
    """Web-optimized video operations built on FFmpegService."""

    def __init__(self):
        self.svc = FFmpegService()

    # ── WebP Frame Extraction ────────────────────────────────

    def extract_frames_webp(
        self,
        input_path: Path,
        output_dir: Path,
        fps: float = 10,
        width: int = 1920,
        quality: int = 82,
    ) -> list[Path]:
        """Extract frames as WebP images at specified FPS.

        WebP at quality 82 offers the best size/quality ratio for scroll sites.
        flags=lanczos uses the highest quality scaling algorithm.

        Args:
            input_path: Source video.
            output_dir: Directory for extracted frames.
            fps: Frames per second to extract.
            width: Target width (-2 preserves aspect ratio).
            quality: WebP quality (82 recommended).

        Returns:
            List of extracted frame paths, sorted by name.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pattern = str(output_dir / "frame_%04d.webp")

        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-vf", f"fps={fps},scale={width}:-2:flags=lanczos",
            "-c:v", "libwebp",
            "-quality", str(quality),
            "-compression_level", "6",
            pattern, "-y",
        ]

        logger.info("Extracting frames: %s → %s (fps=%s, w=%d, q=%d)",
                     input_path.name, output_dir, fps, width, quality)
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)

        frames = sorted(output_dir.glob("frame_*.webp"))
        logger.info("Extracted %d frames", len(frames))
        return frames

    def extract_frames_uniform(
        self,
        input_path: Path,
        output_dir: Path,
        num_frames: int = 60,
        width: int = 1920,
        quality: int = 82,
    ) -> list[Path]:
        """Extract a specific number of frames uniformly distributed.

        First gets video duration via ffprobe, then calculates FPS.
        Example: 60 frames from a 10s video = fps=6.

        Args:
            input_path: Source video.
            output_dir: Output directory.
            num_frames: Total number of frames to extract.
            width: Target width.
            quality: WebP quality.

        Returns:
            List of extracted frame paths.
        """
        meta = self.svc.get_metadata(input_path)
        duration = meta.duration
        if duration <= 0:
            raise ValueError(f"Cannot determine duration of {input_path}")

        fps = num_frames / duration
        return self.extract_frames_webp(input_path, output_dir, fps, width, quality)

    def extract_every_nth_frame(
        self,
        input_path: Path,
        output_dir: Path,
        every_n: int = 3,
        width: int = 1920,
        quality: int = 82,
    ) -> list[Path]:
        """Extract every Nth frame using FFmpeg select filter.

        Args:
            input_path: Source video.
            output_dir: Output directory.
            every_n: Extract every Nth frame (3 = every 3rd frame).
            width: Target width.
            quality: WebP quality.

        Returns:
            List of extracted frame paths.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pattern = str(output_dir / "frame_%04d.webp")

        # -vsync vfr is mandatory with select filter to avoid duplicate frames
        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-vf", f"select='not(mod(n\\,{every_n}))',scale={width}:-2:flags=lanczos",
            "-vsync", "vfr",
            "-c:v", "libwebp",
            "-quality", str(quality),
            pattern, "-y",
        ]

        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        frames = sorted(output_dir.glob("frame_*.webp"))
        logger.info("Extracted %d frames (every %dth)", len(frames), every_n)
        return frames

    # ── Poster & Thumbnail ───────────────────────────────────

    def extract_poster(
        self,
        input_path: Path,
        output_path: Path,
        width: int = 1280,
        quality: int = 85,
    ) -> Path:
        """Extract first frame as poster image (WebP).

        Args:
            input_path: Source video.
            output_path: Poster output path (.webp recommended).
            width: Poster width.
            quality: WebP quality.

        Returns:
            Path to poster image.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-frames:v", "1",
            "-vf", f"scale={width}:-2",
            "-q:v", str(quality),
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Poster extraction failed: {output_path}")

        return output_path

    def extract_thumbnail(
        self,
        input_path: Path,
        output_path: Path,
        timestamp: float = 5.0,
        quality: int = 2,
    ) -> Path:
        """Extract thumbnail at specific timestamp.

        Args:
            input_path: Source video.
            output_path: Thumbnail output (jpg recommended).
            timestamp: Seconds into video.
            quality: JPEG quality (2 = high quality for -q:v).

        Returns:
            Path to thumbnail.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-ss", str(timestamp),
            "-i", str(input_path),
            "-frames:v", "1",
            "-q:v", str(quality),
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return output_path

    def generate_sprite_sheet(
        self,
        input_path: Path,
        output_path: Path,
        fps: float = 0.1,
        tile: str = "10x10",
        thumb_width: int = 160,
    ) -> Path:
        """Generate sprite sheet for seek bar previews.

        Args:
            input_path: Source video.
            output_path: Sprite sheet output (jpg).
            fps: Frame extraction rate (0.1 = 1 every 10s).
            tile: Grid layout (e.g., "10x10").
            thumb_width: Width of each thumbnail in grid.

        Returns:
            Path to sprite sheet.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-vf", f"fps={fps},scale={thumb_width}:-1,tile={tile}",
            "-frames:v", "1",
            "-q:v", "5",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        return output_path

    # ── Web Video Optimization ───────────────────────────────

    def optimize_mp4_web(
        self,
        input_path: Path,
        output_path: Path,
        width: int = 1920,
        crf: int = 23,
    ) -> Path:
        """Optimize MP4 for web delivery (H.264, faststart, no audio).

        -movflags +faststart moves the moov atom to the beginning
        for progressive HTTP loading.

        Args:
            input_path: Source video.
            output_path: Optimized output.
            width: Target width.
            crf: Constant Rate Factor (23 for 1080p).

        Returns:
            Path to optimized video.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-c:v", "libx264", "-crf", str(crf),
            "-preset", "slow", "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={width}:-2:flags=lanczos",
            "-movflags", "+faststart",
            "-an",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        return output_path

    def encode_webm_vp9(
        self,
        input_path: Path,
        output_path: Path,
        width: int = 1920,
        crf: int = 31,
    ) -> Path:
        """Encode to WebM VP9 for modern browsers (better compression).

        Args:
            input_path: Source video.
            output_path: WebM output.
            width: Target width.
            crf: VP9 CRF (31 for 1080p).

        Returns:
            Path to WebM file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-i", str(input_path),
            "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
            "-vf", f"scale={width}:-2",
            "-deadline", "good", "-cpu-used", "2", "-row-mt", "1",
            "-an",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)
        return output_path

    # ── GIF for Ad Previews ──────────────────────────────────

    def create_preview_gif(
        self,
        input_path: Path,
        output_path: Path,
        start: float = 0,
        duration: float = 5,
        width: int = 480,
        fps: int = 12,
    ) -> Path:
        """Create high-quality animated GIF preview (for ads).

        Uses two-pass palettegen for optimal quality.

        Args:
            input_path: Source video.
            output_path: GIF output.
            start: Start timestamp.
            duration: GIF duration.
            width: GIF width.
            fps: Frame rate.

        Returns:
            Path to GIF.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.svc.ffmpeg,
            "-ss", str(start), "-t", str(duration),
            "-i", str(input_path),
            "-filter_complex",
            f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
            "-loop", "0",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return output_path
