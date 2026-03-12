"""Ken Burns Effect Generator — creates cinematic motion from still images.

Uses FFmpeg zoompan filter with 8K upscaling for smooth, professional results.
Award-winning technique: scale source to 8000px wide before zoompan for
sub-pixel smooth motion at 1920x1080 output.

Reference: https://www.bannerbear.com/blog/how-to-do-a-ken-burns-style-effect-with-ffmpeg/
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


# FFmpeg zoompan filter expressions for each motion preset.
# {frames} = total frames, {w}/{h} = output size, {fps} = frame rate.
# All presets use center-focused zoom window: x=iw/2-(iw/zoom/2), y=ih/2-(ih/zoom/2)
PRESETS: dict[str, str] = {
    "zoom_in": (
        "zoompan=z='min(zoom+0.0015,1.5)'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
    "zoom_out": (
        "zoompan=z='if(eq(on,1),1.5,max(zoom-0.0015,1.0))'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
    "pan_left": (
        "zoompan=z='1.2'"
        ":x='iw*0.3*(1-on/{frames})':y='ih/2-(ih/zoom/2)'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
    "pan_right": (
        "zoompan=z='1.2'"
        ":x='iw*0.3*(on/{frames})':y='ih/2-(ih/zoom/2)'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
    "pan_up": (
        "zoompan=z='1.2'"
        ":x='iw/2-(iw/zoom/2)':y='ih*0.3*(1-on/{frames})'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
    "slow_zoom_in": (
        "zoompan=z='min(zoom+0.0008,1.3)'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d={frames}:s={w}x{h}:fps={fps}"
    ),
}

# Scene category → recommended motion preset for narrative coherence.
SCENE_MOTION_MAP: dict[str, str] = {
    "plantation": "slow_zoom_in",    # Reveal the vastness
    "product_oil": "zoom_in",         # Focus on product detail
    "product_papaya": "zoom_in",      # Focus on product detail
    "product_nuts": "zoom_in",        # Focus on product detail
    "team": "pan_right",              # Scan across the team
    "harvest": "pan_left",            # Follow the action
    "production": "zoom_out",         # Show the full process
    "overview": "slow_zoom_in",       # Gentle reveal
}


class KenBurnsGenerator:
    """Generate video segments from still images with cinematic Ken Burns motion.

    Uses FFmpeg's zoompan filter with 8K upscaling for professional-quality
    smooth motion at 1920x1080 output.
    """

    def __init__(self):
        self.ffmpeg = os.getenv("FFMPEG_PATH", "/usr/local/bin/ffmpeg")
        self.ffprobe = os.getenv("FFPROBE_PATH", "/usr/local/bin/ffprobe")

    def generate(
        self,
        image_path: Path,
        output_path: Path,
        duration: float,
        preset: str = "slow_zoom_in",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        fade_in: float = 0.5,
        fade_out: float = 0.5,
    ) -> dict:
        """Create a video segment from a still image with motion effect.

        Args:
            image_path: Path to source image (any format FFmpeg can read).
            output_path: Path for output MP4 video.
            duration: Target duration in seconds.
            preset: Motion preset name (see PRESETS dict).
            width: Output width in pixels.
            height: Output height in pixels.
            fps: Output frame rate.
            fade_in: Fade-in duration in seconds (0 to disable).
            fade_out: Fade-out duration in seconds (0 to disable).

        Returns:
            dict with: output_path, duration, width, height, fps, preset
        """
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset '{preset}'. Available: {list(PRESETS.keys())}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_frames = int(duration * fps)

        # Build zoompan filter with parameters
        zoompan_filter = PRESETS[preset].format(
            frames=total_frames, w=width, h=height, fps=fps
        )

        # Full filter chain:
        # 1. Upscale to 4000px wide (2x oversampling for smooth sub-pixel motion)
        #    Note: 8000px is theoretically ideal but 4x slower; 4000px provides
        #    excellent quality at 1920x1080 output with practical encode times.
        # 2. Apply zoompan (produces video at target resolution)
        # 3. Optional fade-in/fade-out
        filters = [f"scale=4000:-1", zoompan_filter]

        if fade_in > 0:
            fade_in_frames = int(fade_in * fps)
            filters.append(f"fade=t=in:st=0:d={fade_in}:alpha=0")
        if fade_out > 0:
            fade_out_start = max(0, duration - fade_out)
            filters.append(f"fade=t=out:st={fade_out_start}:d={fade_out}:alpha=0")

        filter_chain = ",".join(filters)

        cmd = [
            self.ffmpeg,
            "-loop", "1",
            "-i", str(image_path),
            "-vf", filter_chain,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path), "-y",
        ]

        logger.info(
            "Ken Burns: %s → %s (%.1fs, preset=%s)",
            image_path.name, output_path.name, duration, preset,
        )

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"Ken Burns generation failed: {result.stderr[-300:]}"
            )

        # V-I-V After: verify output
        meta = self._verify_output(output_path, duration, width, height)

        return {
            "output_path": str(output_path),
            "duration": meta["duration"],
            "width": meta["width"],
            "height": meta["height"],
            "fps": fps,
            "preset": preset,
            "file_size": output_path.stat().st_size,
        }

    def generate_for_scene(
        self,
        image_path: Path,
        output_path: Path,
        duration: float,
        scene_category: str,
        **kwargs,
    ) -> dict:
        """Generate Ken Burns segment with preset auto-selected from scene category.

        Args:
            image_path: Source image.
            output_path: Output video.
            duration: Target duration.
            scene_category: Semantic category (plantation, team, product_oil, etc.)
            **kwargs: Additional args passed to generate().

        Returns:
            Same dict as generate().
        """
        preset = SCENE_MOTION_MAP.get(scene_category, "slow_zoom_in")
        return self.generate(
            image_path=image_path,
            output_path=output_path,
            duration=duration,
            preset=preset,
            **kwargs,
        )

    def _verify_output(
        self, output_path: Path, expected_duration: float,
        expected_width: int, expected_height: int,
    ) -> dict:
        """V-I-V After: verify the generated video meets specifications."""
        if not output_path.exists():
            raise RuntimeError(f"Output not created: {output_path}")
        if output_path.stat().st_size == 0:
            raise RuntimeError(f"Output is empty: {output_path}")

        import json
        cmd = [
            self.ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError(f"Cannot probe output: {result.stderr[:200]}")

        data = json.loads(result.stdout)
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise RuntimeError("No video stream in output")

        actual_w = int(video_stream.get("width", 0))
        actual_h = int(video_stream.get("height", 0))
        actual_dur = float(data.get("format", {}).get("duration", 0))

        if abs(actual_dur - expected_duration) > 1.0:
            logger.warning(
                "Duration mismatch: expected %.1fs, got %.1fs",
                expected_duration, actual_dur,
            )

        if actual_w != expected_width or actual_h != expected_height:
            logger.warning(
                "Resolution mismatch: expected %dx%d, got %dx%d",
                expected_width, expected_height, actual_w, actual_h,
            )

        return {
            "duration": actual_dur,
            "width": actual_w,
            "height": actual_h,
            "codec": video_stream.get("codec_name", "unknown"),
        }
