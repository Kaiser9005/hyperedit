"""Skill 15: Color Grading.

Apply color grading presets, LUTs, or custom adjustments to video.
Uses FFmpeg eq filter with contrast, brightness, saturation, and gamma.
"""

import argparse
import subprocess
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class ColorGrading:
    """Apply color grading to video files via presets, LUTs, or manual adjustments."""

    PRESETS = {
        "warm": {"contrast": 1.05, "brightness": 0.02, "saturation": 1.15, "gamma": 0.95},
        "cool": {"contrast": 1.05, "brightness": 0.0, "saturation": 0.9, "gamma": 1.05},
        "cinematic": {"contrast": 1.15, "brightness": -0.03, "saturation": 0.85, "gamma": 1.1},
        "vintage": {"contrast": 0.9, "brightness": 0.05, "saturation": 0.7, "gamma": 0.9},
        "high_contrast": {"contrast": 1.3, "brightness": 0.0, "saturation": 1.1, "gamma": 1.0},
        "desaturated": {"contrast": 1.0, "brightness": 0.0, "saturation": 0.3, "gamma": 1.0},
    }

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        preset: Optional[str] = None,
        lut_path: Optional[Path] = None,
        contrast: float = 1.0,
        brightness: float = 0.0,
        saturation: float = 1.0,
        gamma: float = 1.0,
    ) -> dict:
        """Full V-I-V cycle for color grading.

        Args:
            input_path: Source video file.
            output_path: Destination for graded video.
            preset: Named preset (warm, cool, cinematic, vintage, high_contrast, desaturated).
            lut_path: Path to a .cube or .3dl LUT file.
            contrast: Contrast adjustment (0.0-3.0, default 1.0).
            brightness: Brightness adjustment (-1.0 to 1.0, default 0.0).
            saturation: Saturation adjustment (0.0-3.0, default 1.0).
            gamma: Gamma correction (0.1-10.0, default 1.0).

        Returns:
            dict with input/output durations, preset used, adjustments, and QA results.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        # get_metadata raises ValueError if no video stream found

        if lut_path is not None:
            lut_path = Path(lut_path)
            if not lut_path.exists():
                raise FileNotFoundError(f"LUT file not found: {lut_path}")

        input_duration = meta.duration

        # === IMPLEMENT ===
        if preset is not None:
            if preset not in self.PRESETS:
                raise ValueError(
                    f"Unknown preset '{preset}'. Available: {list(self.PRESETS.keys())}"
                )
            preset_vals = self.PRESETS[preset]
            # Preset values are used as base; explicit non-default params override
            c = contrast if contrast != 1.0 else preset_vals["contrast"]
            b = brightness if brightness != 0.0 else preset_vals["brightness"]
            s = saturation if saturation != 1.0 else preset_vals["saturation"]
            g = gamma if gamma != 1.0 else preset_vals["gamma"]
            adjustments = {"contrast": c, "brightness": b, "saturation": s, "gamma": g}
            self._apply_color_adjustment(input_path, output_path, c, b, s, g)
            preset_used = preset
        elif lut_path is not None:
            self.ffmpeg.apply_lut(input_path, output_path, lut_path)
            adjustments = {"lut_file": str(lut_path)}
            preset_used = None
        else:
            adjustments = {
                "contrast": contrast,
                "brightness": brightness,
                "saturation": saturation,
                "gamma": gamma,
            }
            self._apply_color_adjustment(
                input_path, output_path, contrast, brightness, saturation, gamma
            )
            preset_used = None

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
            "input_duration": input_duration,
            "output_duration": output_duration,
            "preset_used": preset_used,
            "adjustments": adjustments,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def _apply_color_adjustment(
        self,
        input_path: Path,
        output_path: Path,
        contrast: float,
        brightness: float,
        saturation: float,
        gamma: float,
    ) -> Path:
        """Apply eq filter with contrast, brightness, saturation, and gamma.

        Uses a direct FFmpeg call because the existing FFmpegService.color_adjust
        method does not support the gamma parameter.
        """
        eq_filter = (
            f"eq=contrast={contrast}:brightness={brightness}"
            f":saturation={saturation}:gamma={gamma}"
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

    def list_presets(self) -> dict:
        """Return all available color grading presets."""
        return dict(self.PRESETS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply color grading to video")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--preset", default=None, help="Named preset to apply")
    parser.add_argument("--lut", default=None, help="Path to .cube/.3dl LUT file")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast (0.0-3.0)")
    parser.add_argument("--brightness", type=float, default=0.0, help="Brightness (-1.0 to 1.0)")
    parser.add_argument("--saturation", type=float, default=1.0, help="Saturation (0.0-3.0)")
    parser.add_argument("--gamma", type=float, default=1.0, help="Gamma (0.1-10.0)")

    args = parser.parse_args()

    skill = ColorGrading()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        preset=args.preset,
        lut_path=Path(args.lut) if args.lut else None,
        contrast=args.contrast,
        brightness=args.brightness,
        saturation=args.saturation,
        gamma=args.gamma,
    )

    print("\n=== Color Grading Complete ===")
    if result["preset_used"]:
        print(f"Preset: {result['preset_used']}")
    print(f"Adjustments: {result['adjustments']}")
    print(f"Duration: {result['input_duration']:.1f}s -> {result['output_duration']:.1f}s")
    print(f"QA: {sum(1 for r in result['qa_results'] if r['passed'])}/{len(result['qa_results'])} checks passed")
