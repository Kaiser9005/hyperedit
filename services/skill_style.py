"""Skill 6: Video Style Transfer.

Clone the visual style of a reference video onto a target video,
or apply curated style presets using FFmpeg filter chains.
"""

import argparse
import re
import subprocess
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class StyleTransfer:
    """Apply visual style presets or clone a reference video's look."""

    STYLE_PRESETS = {
        "film_noir": {
            "name": "Film Noir",
            "filters": "eq=saturation=0:contrast=1.4:brightness=-0.05:gamma=1.2",
        },
        "vhs_retro": {
            "name": "VHS Retro",
            "filters": "eq=saturation=0.7:contrast=0.9:brightness=0.03,noise=c0s=15:allf=t,unsharp=3:3:0.5",
        },
        "instagram_warm": {
            "name": "Instagram Warm",
            "filters": "eq=saturation=1.3:contrast=1.1:brightness=0.04:gamma=0.9,colorbalance=rs=0.1:gs=0.05:bs=-0.1",
        },
        "cool_blue": {
            "name": "Cool Blue",
            "filters": "eq=saturation=0.9:contrast=1.05,colorbalance=rs=-0.1:gs=0:bs=0.15",
        },
        "high_contrast_bw": {
            "name": "High Contrast B&W",
            "filters": "eq=saturation=0:contrast=1.6:brightness=-0.02:gamma=1.3",
        },
        "dreamy": {
            "name": "Dreamy",
            "filters": "eq=saturation=1.1:brightness=0.05:gamma=0.85,gblur=sigma=1.5",
        },
        "cinematic_teal_orange": {
            "name": "Cinematic Teal & Orange",
            "filters": "eq=contrast=1.15:saturation=1.1,colorbalance=rs=0.1:gs=-0.05:bs=-0.1:rh=0.05:gh=-0.03:bh=0.08",
        },
    }

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        style: Optional[str] = None,
        reference_path: Optional[Path] = None,
    ) -> dict:
        """Full V-I-V cycle for style transfer.

        Args:
            input_path: Source video file.
            output_path: Destination for styled video.
            style: Named style preset key from STYLE_PRESETS.
            reference_path: Path to a reference video whose look to clone.

        Returns:
            dict with style_applied, input_duration, output_duration.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        if style is None and reference_path is None:
            raise ValueError(
                "Either 'style' preset or 'reference_path' must be provided."
            )

        meta = self.ffmpeg.get_metadata(input_path)
        input_duration = meta.duration

        if reference_path is not None:
            reference_path = Path(reference_path)
            if not reference_path.exists():
                raise FileNotFoundError(
                    f"Reference video not found: {reference_path}"
                )

        # === IMPLEMENT ===
        if style is not None:
            if style not in self.STYLE_PRESETS:
                raise ValueError(
                    f"Unknown style '{style}'. "
                    f"Available: {list(self.STYLE_PRESETS.keys())}"
                )
            self._apply_style_preset(input_path, output_path, style)
            style_applied = self.STYLE_PRESETS[style]["name"]
        else:
            ref_stats = self._analyze_reference(reference_path)
            self._match_style(input_path, output_path, ref_stats)
            style_applied = f"Reference match ({reference_path.name})"

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"Output file was not created: {output_path}")

        out_meta = self.ffmpeg.get_metadata(output_path)
        output_duration = out_meta.duration

        # Resolution check
        if out_meta.width != meta.width or out_meta.height != meta.height:
            raise RuntimeError(
                f"Resolution mismatch: input {meta.width}x{meta.height} "
                f"vs output {out_meta.width}x{out_meta.height}"
            )

        # Duration check (0.5s tolerance)
        if abs(input_duration - output_duration) > 0.5:
            raise RuntimeError(
                f"Duration mismatch: input {input_duration:.2f}s "
                f"vs output {output_duration:.2f}s"
            )

        qa_results = self.qa.full_check(
            output_path,
            expected_duration=input_duration,
            min_width=meta.width,
            min_height=meta.height,
        )

        return {
            "style_applied": style_applied,
            "input_duration": input_duration,
            "output_duration": output_duration,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def _apply_style_preset(
        self,
        input_path: Path,
        output_path: Path,
        preset_name: str,
    ) -> Path:
        """Apply a named style preset's filter chain via FFmpeg."""
        preset = self.STYLE_PRESETS[preset_name]
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", preset["filters"],
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _analyze_reference(self, reference_path: Path) -> dict:
        """Get basic color stats from reference video using FFmpeg signalstats.

        Extracts YAVG (luma/brightness), UAVG and VAVG (chroma) averages
        across frames by running signalstats and parsing the output.

        Returns:
            dict with keys 'yavg', 'uavg', 'vavg' as float averages.
        """
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(reference_path),
            "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:key=lavfi.signalstats.UAVG:key=lavfi.signalstats.VAVG",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr

        # Parse YAVG, UAVG, VAVG values from metadata output lines
        yavg_values = [float(m) for m in re.findall(r"lavfi\.signalstats\.YAVG=(\d+\.?\d*)", stderr)]
        uavg_values = [float(m) for m in re.findall(r"lavfi\.signalstats\.UAVG=(\d+\.?\d*)", stderr)]
        vavg_values = [float(m) for m in re.findall(r"lavfi\.signalstats\.VAVG=(\d+\.?\d*)", stderr)]

        stats = {
            "yavg": sum(yavg_values) / len(yavg_values) if yavg_values else 128.0,
            "uavg": sum(uavg_values) / len(uavg_values) if uavg_values else 128.0,
            "vavg": sum(vavg_values) / len(vavg_values) if vavg_values else 128.0,
        }
        return stats

    def _match_style(
        self,
        input_path: Path,
        output_path: Path,
        reference_stats: dict,
    ) -> Path:
        """Adjust input video to approximate the reference video's color stats.

        Maps reference YAVG/UAVG/VAVG stats to FFmpeg eq filter parameters:
        - YAVG (0-255) -> brightness adjustment
        - UAVG/VAVG deviation from neutral (128) -> saturation adjustment
        - Overall contrast estimated from brightness level
        """
        yavg = reference_stats.get("yavg", 128.0)
        uavg = reference_stats.get("uavg", 128.0)
        vavg = reference_stats.get("vavg", 128.0)

        # Map YAVG to brightness: neutral is ~128, scale to -0.5..+0.5
        brightness = (yavg - 128.0) / 256.0

        # Map chroma deviation to saturation adjustment
        # Larger deviation from 128 means more saturated reference
        chroma_deviation = (abs(uavg - 128.0) + abs(vavg - 128.0)) / 2.0
        # Scale: 0 deviation = 0.5 sat, 30+ deviation = 1.5 sat
        saturation = 0.5 + min(chroma_deviation / 30.0, 1.0)

        # Contrast: brighter references tend to have lower contrast
        if yavg > 140:
            contrast = 0.95
        elif yavg < 100:
            contrast = 1.15
        else:
            contrast = 1.0

        eq_filter = (
            f"eq=contrast={contrast:.2f}"
            f":brightness={brightness:.4f}"
            f":saturation={saturation:.2f}"
        )

        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", eq_filter,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def list_styles(self) -> dict:
        """Return all available style presets."""
        return dict(self.STYLE_PRESETS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apply visual style transfer to video"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument(
        "--style", default=None,
        help="Named style preset (film_noir, vhs_retro, instagram_warm, "
             "cool_blue, high_contrast_bw, dreamy, cinematic_teal_orange)",
    )
    parser.add_argument(
        "--reference", default=None,
        help="Path to reference video whose style to clone",
    )

    args = parser.parse_args()

    skill = StyleTransfer()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        style=args.style,
        reference_path=Path(args.reference) if args.reference else None,
    )

    print("\n=== Style Transfer Complete ===")
    print(f"Style applied: {result['style_applied']}")
    print(
        f"Duration: {result['input_duration']:.1f}s -> "
        f"{result['output_duration']:.1f}s"
    )
    qa = result["qa_results"]
    print(
        f"QA: {sum(1 for r in qa if r['passed'])}/{len(qa)} checks passed"
    )
