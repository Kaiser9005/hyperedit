"""Skill 8: Audio Enhancement.

Applies noise reduction, loudness normalization, and background music.
Uses FFmpeg audio filters for processing.
"""

import argparse
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class AudioEnhancement:
    """Enhance audio quality of video files."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        target_lufs: float = -14,
        noise_reduce: bool = True,
        music_path: Optional[Path] = None,
        music_volume: float = 0.15,
    ) -> dict:
        """Full V-I-V cycle for audio enhancement."""
        # === VERIFY (Before) ===
        meta = self.ffmpeg.get_metadata(input_path)
        if not meta.has_audio:
            raise ValueError(f"Input video has no audio track: {input_path}")

        before_loudness = self.ffmpeg.get_loudness(input_path)
        before_lufs = float(before_loudness.get("input_i", -99))

        # === IMPLEMENT ===
        work_dir = output_path.parent
        current = input_path

        # Step 1: Noise reduction
        if noise_reduce:
            nr_output = work_dir / f"{input_path.stem}_nr.mp4"
            self.ffmpeg.noise_reduce(current, nr_output)
            current = nr_output

        # Step 2: Loudness normalization
        norm_output = work_dir / f"{input_path.stem}_norm.mp4"
        self.ffmpeg.normalize_audio(current, norm_output, target_lufs=target_lufs)
        current = norm_output

        # Step 3: Background music (if provided)
        if music_path and music_path.exists():
            music_output = work_dir / f"{input_path.stem}_music.mp4"
            self.ffmpeg.merge_audio(current, music_path, music_output, audio_volume=music_volume)
            current = music_output

        # Move final to output path
        import shutil
        if current != output_path:
            shutil.move(str(current), str(output_path))

        # Cleanup intermediates
        for suffix in ["_nr.mp4", "_norm.mp4", "_music.mp4"]:
            temp = work_dir / f"{input_path.stem}{suffix}"
            if temp.exists() and temp != output_path:
                temp.unlink()

        # === VERIFY (After) ===
        after_loudness = self.ffmpeg.get_loudness(output_path)
        after_lufs = float(after_loudness.get("input_i", -99))
        qa_results = self.qa.full_check(output_path, min_width=meta.width, min_height=meta.height)

        return {
            "before_lufs": before_lufs,
            "after_lufs": after_lufs,
            "target_lufs": target_lufs,
            "lufs_diff": abs(after_lufs - target_lufs),
            "noise_reduced": noise_reduce,
            "music_added": music_path is not None,
            "qa_results": [r.__dict__ for r in qa_results],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance audio in video")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-lufs", type=float, default=-14)
    parser.add_argument("--no-noise-reduce", action="store_true")
    parser.add_argument("--music", default=None)
    parser.add_argument("--music-volume", type=float, default=0.15)

    args = parser.parse_args()

    skill = AudioEnhancement()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        target_lufs=args.target_lufs,
        noise_reduce=not args.no_noise_reduce,
        music_path=Path(args.music) if args.music else None,
        music_volume=args.music_volume,
    )

    print(f"\n=== Audio Enhancement Complete ===")
    print(f"Before: {result['before_lufs']:.1f} LUFS")
    print(f"After:  {result['after_lufs']:.1f} LUFS")
    print(f"Target: {result['target_lufs']:.1f} LUFS (diff: {result['lufs_diff']:.1f})")
