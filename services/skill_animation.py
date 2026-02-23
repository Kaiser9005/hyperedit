"""Skill 5: Animation Overlays.

Add animated text overlays, lower thirds, title cards, scrolling text,
corner badges, and countdown timers to video via FFmpeg drawtext filters.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class AnimationOverlay:
    """Apply animated text overlays to video files using FFmpeg drawtext filters."""

    ANIMATION_PRESETS = {
        "lower_third": {
            "name": "Lower Third",
            "description": "Animated lower-third title bar",
            "filter": "drawtext=text='{text}':fontsize={fontsize}:fontcolor={color}:x=(w-tw)/2:y=h-th-80:enable='between(t,{start},{end})':box=1:boxcolor={bg_color}:boxborderw=15",
        },
        "title_card": {
            "name": "Title Card",
            "description": "Centered title with fade",
            "filter": "drawtext=text='{text}':fontsize={fontsize}:fontcolor={color}:x=(w-tw)/2:y=(h-th)/2:enable='between(t,{start},{end})'",
        },
        "scroll_text": {
            "name": "Scrolling Text",
            "description": "Text scrolling from bottom to top",
            "filter": "drawtext=text='{text}':fontsize={fontsize}:fontcolor={color}:x=(w-tw)/2:y=h-t*{speed}:enable='between(t,{start},{end})'",
        },
        "corner_badge": {
            "name": "Corner Badge",
            "description": "Small badge in corner",
            "filter": "drawtext=text='{text}':fontsize={fontsize}:fontcolor={color}:x=w-tw-20:y=20:enable='between(t,{start},{end})':box=1:boxcolor={bg_color}:boxborderw=8",
        },
        "countdown": {
            "name": "Countdown Timer",
            "description": "Countdown overlay",
            "filter": "drawtext=text='%{{eif\\:({total}-t)\\:d}}':fontsize={fontsize}:fontcolor={color}:x=(w-tw)/2:y=(h-th)/2:enable='between(t,{start},{end})'",
        },
    }

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        overlays: list[dict],
    ) -> dict:
        """Full V-I-V cycle for animation overlays.

        Args:
            input_path: Source video file.
            output_path: Destination for video with overlays.
            overlays: List of overlay spec dicts. Each must have at least:
                - preset: Name of animation preset
                - text: Text to display
                - start: Start time in seconds
                - end: End time in seconds
                Optional keys: fontsize, color, bg_color, speed, total

        Returns:
            dict with overlays_applied count, input_duration, output_duration.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        if not isinstance(overlays, list):
            raise TypeError("overlays must be a list of overlay spec dicts")

        meta = self.ffmpeg.get_metadata(input_path)
        input_duration = meta.duration

        # === IMPLEMENT ===
        if len(overlays) == 0:
            # No overlays requested, copy input to output
            shutil.copy2(str(input_path), str(output_path))
        else:
            # Validate each overlay spec
            for i, overlay in enumerate(overlays):
                if not isinstance(overlay, dict):
                    raise TypeError(f"Overlay {i} must be a dict, got {type(overlay).__name__}")
                preset = overlay.get("preset")
                if preset not in self.ANIMATION_PRESETS:
                    raise ValueError(
                        f"Unknown preset '{preset}' in overlay {i}. "
                        f"Available: {list(self.ANIMATION_PRESETS.keys())}"
                    )
                if "text" not in overlay and preset != "countdown":
                    raise ValueError(f"Overlay {i} missing required 'text' field")
                if "start" not in overlay or "end" not in overlay:
                    raise ValueError(f"Overlay {i} missing required 'start' and/or 'end' fields")

            filter_chain = self._build_filter_chain(overlays, meta.width, meta.height)
            self._apply_filters(input_path, output_path, filter_chain)

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"Output file was not created: {output_path}")

        out_meta = self.ffmpeg.get_metadata(output_path)
        output_duration = out_meta.duration

        # Duration check (0.5s tolerance)
        if abs(input_duration - output_duration) > 0.5:
            raise RuntimeError(
                f"Duration mismatch: input {input_duration:.2f}s "
                f"vs output {output_duration:.2f}s"
            )

        return {
            "overlays_applied": len(overlays),
            "input_duration": input_duration,
            "output_duration": output_duration,
        }

    def _build_filter_chain(
        self,
        overlays: list[dict],
        video_width: int,
        video_height: int,
    ) -> str:
        """Combine multiple drawtext filters into a single filter chain.

        Args:
            overlays: List of overlay spec dicts.
            video_width: Width of the input video.
            video_height: Height of the input video.

        Returns:
            Comma-separated FFmpeg filter string.
        """
        filters = []
        for overlay in overlays:
            preset_key = overlay["preset"]
            preset = self.ANIMATION_PRESETS[preset_key]
            template = preset["filter"]

            # Build substitution values with defaults
            params = {
                "text": overlay.get("text", ""),
                "fontsize": overlay.get("fontsize", 48),
                "color": overlay.get("color", "white"),
                "bg_color": overlay.get("bg_color", "black@0.7"),
                "start": overlay["start"],
                "end": overlay["end"],
                "speed": overlay.get("speed", 80),
                "total": overlay.get("total", overlay["end"] - overlay["start"]),
            }

            rendered = template.format(**params)
            filters.append(rendered)

        return ",".join(filters)

    def _apply_filters(
        self,
        input_path: Path,
        output_path: Path,
        filter_chain: str,
    ) -> Path:
        """Run FFmpeg with the assembled drawtext filter chain.

        Args:
            input_path: Source video.
            output_path: Destination video.
            filter_chain: Comma-separated FFmpeg filter string.

        Returns:
            Path to the output file.
        """
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", filter_chain,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def list_presets(self) -> dict:
        """Return all available animation presets."""
        return dict(self.ANIMATION_PRESETS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add animated text overlays to video"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument(
        "--overlay",
        action="append",
        required=True,
        help="Overlay spec as JSON string (can specify multiple)",
    )

    args = parser.parse_args()

    overlay_specs = [json.loads(o) for o in args.overlay]

    skill = AnimationOverlay()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        overlays=overlay_specs,
    )

    print("\n=== Animation Overlays Complete ===")
    print(f"Overlays applied: {result['overlays_applied']}")
    print(f"Duration: {result['input_duration']:.1f}s -> {result['output_duration']:.1f}s")
