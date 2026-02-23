"""Skill 11: Multi-Format Export.

Export video to multiple formats and resolutions for different platforms.
Supports YouTube (4K/1080p/720p), Instagram Reels, TikTok, Twitter,
web-optimized MP4, and GIF preview.
"""

import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class MultiFormatExporter:
    """Export video to platform-specific formats and resolutions."""

    EXPORT_PROFILES = {
        "youtube_4k": {
            "width": 3840, "height": 2160, "fps": 30,
            "bitrate": "20M", "codec": "libx264",
            "audio_bitrate": "320k", "ext": "mp4",
        },
        "youtube_1080p": {
            "width": 1920, "height": 1080, "fps": 30,
            "bitrate": "8M", "codec": "libx264",
            "audio_bitrate": "192k", "ext": "mp4",
        },
        "youtube_720p": {
            "width": 1280, "height": 720, "fps": 30,
            "bitrate": "5M", "codec": "libx264",
            "audio_bitrate": "128k", "ext": "mp4",
        },
        "instagram_reels": {
            "width": 1080, "height": 1920, "fps": 30,
            "bitrate": "6M", "codec": "libx264",
            "audio_bitrate": "192k", "ext": "mp4",
        },
        "tiktok": {
            "width": 1080, "height": 1920, "fps": 30,
            "bitrate": "6M", "codec": "libx264",
            "audio_bitrate": "192k", "ext": "mp4",
        },
        "twitter": {
            "width": 1280, "height": 720, "fps": 30,
            "bitrate": "5M", "codec": "libx264",
            "audio_bitrate": "128k", "ext": "mp4",
        },
        "web_optimized": {
            "width": 1920, "height": 1080, "fps": 30,
            "bitrate": "4M", "codec": "libx264",
            "audio_bitrate": "128k", "ext": "mp4",
        },
        "gif_preview": {
            "width": 480, "height": 270, "fps": 10,
            "bitrate": None, "codec": None,
            "audio_bitrate": None, "ext": "gif",
        },
    }

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_dir: Path,
        profiles: Optional[list[str]] = None,
    ) -> dict:
        """Export video to multiple profiles (V-I-V cycle).

        Args:
            input_path: Source video file.
            output_dir: Directory for exported files.
            profiles: List of profile names. Defaults to youtube_1080p + web_optimized.

        Returns:
            Dict with exports list, each containing profile, path, size_bytes, duration.
        """
        if profiles is None:
            profiles = ["youtube_1080p", "web_optimized"]

        # Validate all profiles before starting
        for name in profiles:
            if name not in self.EXPORT_PROFILES:
                raise ValueError(
                    f"Unknown profile '{name}'. "
                    f"Available: {', '.join(self.EXPORT_PROFILES.keys())}"
                )

        # === VERIFY (Before) ===
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        meta = self.ffmpeg.get_metadata(input_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # === IMPLEMENT ===
        exports = []
        total_size = 0

        for name in profiles:
            profile = self.EXPORT_PROFILES[name]
            ext = profile["ext"]
            output_path = output_dir / f"{input_path.stem}_{name}.{ext}"

            if ext == "gif":
                self._transcode_gif(input_path, output_path, profile)
            else:
                self._transcode(input_path, output_path, profile)

            # === VERIFY (After, per export) ===
            out_size = output_path.stat().st_size
            if ext == "gif":
                duration = meta.duration
            else:
                out_meta = self.ffmpeg.get_metadata(output_path)
                duration = out_meta.duration

            exports.append({
                "profile": name,
                "path": str(output_path),
                "size_bytes": out_size,
                "duration": round(duration, 2),
            })
            total_size += out_size

        return {
            "exports": exports,
            "total_size_bytes": total_size,
        }

    def export_single(
        self,
        input_path: Path,
        output_path: Path,
        profile_name: str,
    ) -> dict:
        """Export video to a single profile.

        Args:
            input_path: Source video file.
            output_path: Destination file path.
            profile_name: Name of the export profile.

        Returns:
            Dict with profile, path, size_bytes, duration.
        """
        if profile_name not in self.EXPORT_PROFILES:
            raise ValueError(
                f"Unknown profile '{profile_name}'. "
                f"Available: {', '.join(self.EXPORT_PROFILES.keys())}"
            )

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        profile = self.EXPORT_PROFILES[profile_name]
        meta = self.ffmpeg.get_metadata(input_path)

        if profile["ext"] == "gif":
            self._transcode_gif(input_path, output_path, profile)
            duration = meta.duration
        else:
            self._transcode(input_path, output_path, profile)
            out_meta = self.ffmpeg.get_metadata(output_path)
            duration = out_meta.duration

        return {
            "profile": profile_name,
            "path": str(output_path),
            "size_bytes": output_path.stat().st_size,
            "duration": round(duration, 2),
        }

    def _transcode(self, input_path: Path, output_path: Path, profile: dict) -> Path:
        """Transcode video to target profile using FFmpeg."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", f"scale={profile['width']}:{profile['height']}:force_original_aspect_ratio=decrease,pad={profile['width']}:{profile['height']}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(profile["fps"]),
            "-c:v", profile["codec"],
            "-b:v", profile["bitrate"],
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", profile["audio_bitrate"],
            "-movflags", "+faststart",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _transcode_gif(self, input_path: Path, output_path: Path, profile: dict) -> Path:
        """Convert video to GIF with palette generation for quality."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            palette_path = tmp.name

        try:
            # Step 1: Generate palette
            palette_cmd = [
                self.ffmpeg.ffmpeg,
                "-i", str(input_path),
                "-vf", f"fps={profile['fps']},scale={profile['width']}:{profile['height']}:flags=lanczos,palettegen",
                str(palette_path), "-y",
            ]
            subprocess.run(palette_cmd, capture_output=True, check=True)

            # Step 2: Use palette to create high-quality GIF
            gif_cmd = [
                self.ffmpeg.ffmpeg,
                "-i", str(input_path),
                "-i", palette_path,
                "-lavfi", f"fps={profile['fps']},scale={profile['width']}:{profile['height']}:flags=lanczos [x]; [x][1:v] paletteuse",
                str(output_path), "-y",
            ]
            subprocess.run(gif_cmd, capture_output=True, check=True)
        finally:
            Path(palette_path).unlink(missing_ok=True)

        return output_path

    def list_profiles(self) -> dict:
        """Return all available export profiles."""
        return dict(self.EXPORT_PROFILES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export video to multiple formats")
    parser.add_argument("--input", required=True, help="Source video file")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument(
        "--profiles", nargs="*", default=None,
        help="Profile names (default: youtube_1080p web_optimized)",
    )
    parser.add_argument("--list", action="store_true", help="List available profiles")

    args = parser.parse_args()

    exporter = MultiFormatExporter()

    if args.list:
        profiles = exporter.list_profiles()
        print("Available export profiles:")
        for name, cfg in profiles.items():
            res = f"{cfg['width']}x{cfg['height']}"
            br = cfg['bitrate'] or 'N/A'
            print(f"  {name:20s}  {res:12s}  {br:>5s}  .{cfg['ext']}")
    else:
        result = exporter.execute(
            input_path=Path(args.input),
            output_dir=Path(args.output_dir),
            profiles=args.profiles,
        )

        print(f"\n=== Multi-Format Export Complete ===")
        print(f"Exports: {len(result['exports'])}")
        for exp in result["exports"]:
            size_mb = exp["size_bytes"] / (1024 * 1024)
            print(f"  {exp['profile']:20s}  {size_mb:6.1f} MB  {exp['duration']:.1f}s  {exp['path']}")
        total_mb = result["total_size_bytes"] / (1024 * 1024)
        print(f"\nTotal size: {total_mb:.1f} MB")
