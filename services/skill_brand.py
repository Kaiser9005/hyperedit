"""Skill 16: Brand Kit Manager.

Apply brand identity (watermark, text overlay, colors) to video using FFmpeg.
Supports configurable brand profiles via JSON config files.
"""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


# Default brand config used when no config file is provided
DEFAULT_BRAND_CONFIG = {
    "name": "Default Brand",
    "colors": {
        "primary": "#166534",
        "secondary": "#D97706",
        "accent": "#78350F",
        "text": "#FFFFFF",
    },
    "fonts": {
        "heading": "Arial",
        "body": "Arial",
    },
    "watermark": {
        "text": "",
        "position": "bottom_right",
        "opacity": 0.3,
        "font_size": 24,
    },
    "text_overlay": {
        "font_size": 36,
        "font_color": "#FFFFFF",
        "bg_color": "#00000080",
        "padding": 10,
    },
}

# Position mapping for drawtext filter coordinates
POSITION_MAP = {
    "bottom_right": "x=w-tw-20:y=h-th-20",
    "bottom_left": "x=20:y=h-th-20",
    "top_right": "x=w-tw-20:y=20",
    "top_left": "x=20:y=20",
    "center": "x=(w-tw)/2:y=(h-th)/2",
}


class BrandKitManager:
    """Apply brand identity to videos via FFmpeg filters."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def load_config(self, config_path: Path) -> dict:
        """Load brand JSON config. Returns default config if path doesn't exist."""
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return DEFAULT_BRAND_CONFIG.copy()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        brand_config: Optional[Path] = None,
        add_watermark: bool = True,
        add_text_overlay: bool = False,
        text_content: str = "",
        text_position: str = "bottom_right",
    ) -> dict:
        """Full V-I-V cycle for brand kit application.

        Args:
            input_path: Path to the input video file.
            output_path: Path for the branded output video.
            brand_config: Path to a brand JSON config file. Uses default if None.
            add_watermark: Whether to apply a watermark from the brand config.
            add_text_overlay: Whether to add a text overlay.
            text_content: The text to overlay on the video.
            text_position: Position for the text overlay.

        Returns:
            Dict with input_duration, output_duration, brand_name,
            watermark_applied, text_overlay_applied, and qa_results.
        """
        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        input_duration = meta.duration

        config = self.load_config(brand_config) if brand_config else DEFAULT_BRAND_CONFIG.copy()

        # === IMPLEMENT ===
        filters = []
        watermark_applied = False
        text_overlay_applied = False

        # Build watermark filter
        if add_watermark:
            wm_config = config.get("watermark", {})
            wm_text = wm_config.get("text", "")
            if wm_text:
                wm_filter = self._build_watermark_filter(wm_config)
                filters.append(wm_filter)
                watermark_applied = True

        # Build text overlay filter
        if add_text_overlay and text_content:
            overlay_config = config.get("text_overlay", {})
            text_filter = self._build_text_overlay_filter(
                overlay_config, text_content, text_position
            )
            filters.append(text_filter)
            text_overlay_applied = True

        # Apply filters via FFmpeg
        self._apply_filters(input_path, output_path, filters)

        # === VERIFY (After) ===
        out_meta = self.ffmpeg.get_metadata(output_path)
        qa_results = self.qa.full_check(
            output_path,
            expected_duration=input_duration,
            min_width=meta.width,
            min_height=meta.height,
        )

        return {
            "input_duration": input_duration,
            "output_duration": out_meta.duration,
            "brand_name": config.get("name", "Unknown"),
            "watermark_applied": watermark_applied,
            "text_overlay_applied": text_overlay_applied,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def _build_watermark_filter(self, watermark_config: dict) -> str:
        """Build a drawtext filter string for watermark overlay."""
        text = watermark_config.get("text", "")
        position = watermark_config.get("position", "bottom_right")
        opacity = watermark_config.get("opacity", 0.3)
        font_size = watermark_config.get("font_size", 24)

        coords = POSITION_MAP.get(position, POSITION_MAP["bottom_right"])

        # Escape single quotes in text for FFmpeg
        escaped_text = text.replace("'", "'\\''")

        alpha_hex = format(int(opacity * 255), "02x")
        font_color = f"white@{opacity}"

        return (
            f"drawtext=text='{escaped_text}':"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"{coords}"
        )

    def _build_text_overlay_filter(
        self, text_config: dict, text_content: str, position: str
    ) -> str:
        """Build a drawtext filter string for branded text overlay with background box."""
        font_size = text_config.get("font_size", 36)
        font_color = text_config.get("font_color", "#FFFFFF")
        bg_color = text_config.get("bg_color", "#00000080")
        padding = text_config.get("padding", 10)

        coords = POSITION_MAP.get(position, POSITION_MAP["bottom_right"])

        # Escape single quotes in text for FFmpeg
        escaped_text = text_content.replace("'", "'\\''")

        # Parse bg_color with alpha (e.g., #00000080 -> black@0.5)
        bg_alpha = 0.5
        if len(bg_color) == 9 and bg_color.startswith("#"):
            bg_alpha = int(bg_color[7:9], 16) / 255
            bg_color = bg_color[:7]

        # Convert hex color to FFmpeg-compatible format
        ffmpeg_font_color = font_color if font_color.startswith("#") else font_color

        return (
            f"drawtext=text='{escaped_text}':"
            f"fontsize={font_size}:"
            f"fontcolor={ffmpeg_font_color}:"
            f"box=1:"
            f"boxcolor=black@{bg_alpha:.2f}:"
            f"boxborderw={padding}:"
            f"{coords}"
        )

    def _apply_filters(
        self, input_path: Path, output_path: Path, filters: list[str]
    ) -> Path:
        """Run FFmpeg with a combined -vf filter chain."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
        ]

        if filters:
            combined = ",".join(filters)
            cmd.extend(["-vf", combined])
            cmd.extend(["-c:v", "libx264", "-preset", "fast"])
        else:
            # No filters -- just re-encode for consistency
            cmd.extend(["-c:v", "libx264", "-preset", "fast"])

        cmd.extend(["-c:a", "copy", str(output_path), "-y"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed (exit {result.returncode}): {result.stderr}"
            )

        return output_path

    def create_brand_config(
        self,
        name: str,
        primary_color: str,
        secondary_color: str,
        output_path: Path,
        accent_color: str = "#78350F",
        watermark_text: str = "",
    ) -> Path:
        """Create a new brand config JSON file.

        Args:
            name: Brand name.
            primary_color: Primary hex color.
            secondary_color: Secondary hex color.
            output_path: Where to write the JSON file.
            accent_color: Accent hex color.
            watermark_text: Default watermark text.

        Returns:
            Path to the created config file.
        """
        config = {
            "name": name,
            "colors": {
                "primary": primary_color,
                "secondary": secondary_color,
                "accent": accent_color,
                "text": "#FFFFFF",
            },
            "fonts": {
                "heading": "Arial",
                "body": "Arial",
            },
            "watermark": {
                "text": watermark_text,
                "position": "bottom_right",
                "opacity": 0.3,
                "font_size": 24,
            },
            "text_overlay": {
                "font_size": 36,
                "font_color": "#FFFFFF",
                "bg_color": "#00000080",
                "padding": 10,
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)

        return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply brand kit to video")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--brand-config", default=None, help="Brand JSON config path")
    parser.add_argument("--no-watermark", action="store_true", help="Skip watermark")
    parser.add_argument("--text-overlay", action="store_true", help="Add text overlay")
    parser.add_argument("--text", default="", help="Text content for overlay")
    parser.add_argument(
        "--text-position",
        default="bottom_right",
        choices=["bottom_left", "bottom_right", "top_left", "top_right", "center"],
        help="Position for text overlay",
    )

    args = parser.parse_args()

    manager = BrandKitManager()
    result = manager.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        brand_config=Path(args.brand_config) if args.brand_config else None,
        add_watermark=not args.no_watermark,
        add_text_overlay=args.text_overlay,
        text_content=args.text,
        text_position=args.text_position,
    )

    print("\n=== Brand Kit Applied ===")
    print(f"Brand: {result['brand_name']}")
    print(f"Watermark: {'Yes' if result['watermark_applied'] else 'No'}")
    print(f"Text overlay: {'Yes' if result['text_overlay_applied'] else 'No'}")
    print(f"Duration: {result['input_duration']:.1f}s -> {result['output_duration']:.1f}s")
