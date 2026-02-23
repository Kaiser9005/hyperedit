"""Skill 9: B-Roll Insertion.

Inserts B-roll footage at detected silence/transition points in video.
Uses whisper.cpp for silence detection and FFmpeg for cutting/assembly.
"""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from whisper_service import WhisperService
from quality_assurance import QualityAssurance


class BRollInserter:
    """Insert B-roll clips at silence gaps or manual timestamps."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.whisper = WhisperService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        broll_clips: list[Path],
        mode: str = "silence",
        max_insertions: int = 5,
        min_gap: float = 2.0,
        manual_points: Optional[list[dict]] = None,
    ) -> dict:
        """
        Full V-I-V cycle for B-roll insertion.

        Args:
            input_path: Path to the main video.
            output_path: Path for the output video.
            broll_clips: List of B-roll video file paths.
            mode: "silence" for auto-detection or "manual" for provided timestamps.
            max_insertions: Maximum number of B-roll insertions.
            min_gap: Minimum silence gap duration (seconds) for silence mode.
            manual_points: List of {"start", "end"} dicts for manual mode.

        Returns:
            Dict with insertions_count, input_duration, output_duration,
            insertion_points.
        """
        # === VERIFY (Before) ===
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        if not broll_clips:
            raise ValueError("At least one B-roll clip path is required")

        resolved_clips = []
        for clip_path in broll_clips:
            clip_path = Path(clip_path)
            if not clip_path.exists():
                raise FileNotFoundError(f"B-roll clip not found: {clip_path}")
            resolved_clips.append(clip_path)

        meta = self.ffmpeg.get_metadata(input_path)
        input_duration = meta.duration

        # === IMPLEMENT ===
        # 1. Find insertion points
        if mode == "manual":
            if not manual_points:
                raise ValueError("manual_points required when mode='manual'")
            insertion_points = [
                {
                    "start": p["start"],
                    "end": p["end"],
                    "duration": p["end"] - p["start"],
                    "type": "manual",
                }
                for p in manual_points
            ]
        else:
            insertion_points = self.find_insertion_points(
                input_path, mode=mode, min_gap=min_gap
            )

        # Limit to max_insertions
        insertion_points = insertion_points[:max_insertions]

        if not insertion_points:
            # No insertion points found -- copy input to output
            shutil.copy2(input_path, output_path)
            return {
                "insertions_count": 0,
                "input_duration": input_duration,
                "output_duration": input_duration,
                "insertion_points": [],
            }

        # 2. Build edit list
        edit_list = self._build_edit_list(
            insertion_points, resolved_clips, input_duration
        )

        # 3. Assemble
        self._assemble(edit_list, output_path, input_path, meta.width, meta.height)

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"Output was not created: {output_path}")

        output_meta = self.ffmpeg.get_metadata(output_path)

        return {
            "insertions_count": len(insertion_points),
            "input_duration": input_duration,
            "output_duration": output_meta.duration,
            "insertion_points": insertion_points,
        }

    def find_insertion_points(
        self,
        input_path: Path,
        mode: str = "silence",
        min_gap: float = 2.0,
    ) -> list[dict]:
        """
        Analyze video for B-roll insertion opportunities.

        Args:
            input_path: Path to the video to analyze.
            mode: Detection mode ("silence").
            min_gap: Minimum gap duration in seconds.

        Returns:
            List of {"start", "end", "duration", "type"} dicts.
        """
        input_path = Path(input_path)

        if mode == "silence":
            # Extract audio for silence detection
            work_dir = input_path.parent
            audio_path = work_dir / f"{input_path.stem}_broll_audio.wav"
            self.whisper.extract_audio(input_path, audio_path)

            silences = self.whisper.detect_silence(
                audio_path,
                noise_db=-40,
                min_duration=min_gap,
            )

            # Cleanup temp audio
            if audio_path.exists():
                audio_path.unlink()

            return [
                {
                    "start": s["start"],
                    "end": s["end"],
                    "duration": s["end"] - s["start"],
                    "type": "silence",
                }
                for s in silences
            ]
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _prepare_broll(
        self,
        broll_path: Path,
        target_duration: float,
        target_width: int,
        target_height: int,
    ) -> Path:
        """
        Trim/loop B-roll to target duration and scale to match main video.

        Args:
            broll_path: Path to the B-roll clip.
            target_duration: Desired duration in seconds.
            target_width: Target width in pixels.
            target_height: Target height in pixels.

        Returns:
            Path to the prepared B-roll clip (temp file).
        """
        broll_path = Path(broll_path)
        broll_meta = self.ffmpeg.get_metadata(broll_path)

        # Create temp output
        tmp = tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False, dir=broll_path.parent
        )
        tmp_path = Path(tmp.name)
        tmp.close()

        # Build scale filter
        scale_filters = []
        if broll_meta.width != target_width or broll_meta.height != target_height:
            scale_filters.append(
                f"scale={target_width}:{target_height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2"
            )

        if broll_meta.duration >= target_duration:
            # Trim to target duration
            vf = ",".join(scale_filters) if scale_filters else None
            cmd = [
                self.ffmpeg.ffmpeg,
                "-i", str(broll_path),
                "-t", str(target_duration),
            ]
            if vf:
                cmd.extend(["-vf", vf])
            cmd.extend([
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                str(tmp_path), "-y",
            ])
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            # Loop to reach target duration
            loop_count = int(target_duration / broll_meta.duration) + 1
            vf_parts = [f"loop={loop_count}:size=32767:start=0"]
            vf_parts.extend(scale_filters)
            vf = ",".join(vf_parts)
            cmd = [
                self.ffmpeg.ffmpeg,
                "-i", str(broll_path),
                "-vf", vf,
                "-t", str(target_duration),
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                str(tmp_path), "-y",
            ]
            subprocess.run(cmd, capture_output=True, check=True)

        return tmp_path

    def _build_edit_list(
        self,
        insertion_points: list[dict],
        broll_clips: list[Path],
        main_duration: float,
    ) -> list[dict]:
        """
        Create ordered edit list alternating between main footage and B-roll.

        Args:
            insertion_points: List of insertion point dicts (start, end, duration, type).
            broll_clips: List of B-roll clip paths.
            main_duration: Total duration of the main video.

        Returns:
            List of {"type": "main"|"broll", "source": path_str_or_None,
                     "start": float, "end": float} dicts.
        """
        if not insertion_points:
            return [
                {
                    "type": "main",
                    "source": None,
                    "start": 0.0,
                    "end": main_duration,
                }
            ]

        # Sort insertion points by start time
        sorted_points = sorted(insertion_points, key=lambda p: p["start"])

        edit_list = []
        current_pos = 0.0

        for i, point in enumerate(sorted_points):
            # Add main segment before this insertion point
            if point["start"] > current_pos:
                edit_list.append({
                    "type": "main",
                    "source": None,
                    "start": current_pos,
                    "end": point["start"],
                })

            # Add B-roll segment (cycle through available clips)
            broll_index = i % len(broll_clips)
            edit_list.append({
                "type": "broll",
                "source": str(broll_clips[broll_index]),
                "start": point["start"],
                "end": point["end"],
            })

            current_pos = point["end"]

        # Add trailing main segment
        if current_pos < main_duration:
            edit_list.append({
                "type": "main",
                "source": None,
                "start": current_pos,
                "end": main_duration,
            })

        return edit_list

    def _assemble(
        self,
        edit_list: list[dict],
        output_path: Path,
        main_input: Path,
        main_width: int,
        main_height: int,
    ) -> Path:
        """
        Execute the edit list by cutting segments and concatenating.

        Args:
            edit_list: Ordered list of main/broll segment dicts.
            output_path: Path for the final output.
            main_input: Path to the original main video.
            main_width: Main video width for B-roll scaling.
            main_height: Main video height for B-roll scaling.

        Returns:
            Path to the assembled output.
        """
        output_path = Path(output_path)
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        temp_segments = []

        for i, entry in enumerate(edit_list):
            seg_path = work_dir / f"_broll_seg_{i:04d}.mp4"

            if entry["type"] == "main":
                # Cut main video segment
                self.ffmpeg.cut(
                    main_input,
                    seg_path,
                    start=entry["start"],
                    end=entry["end"],
                    reencode=True,
                )
            else:
                # Prepare B-roll: trim/scale to match duration and resolution
                broll_duration = entry["end"] - entry["start"]
                prepared = self._prepare_broll(
                    Path(entry["source"]),
                    target_duration=broll_duration,
                    target_width=main_width,
                    target_height=main_height,
                )
                shutil.move(str(prepared), str(seg_path))

            temp_segments.append(seg_path)

        # Concatenate all segments
        if len(temp_segments) == 1:
            shutil.move(str(temp_segments[0]), str(output_path))
        else:
            self.ffmpeg.concat(temp_segments, output_path)

        # Cleanup temp files
        for f in temp_segments:
            if f.exists():
                f.unlink()

        return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Insert B-roll at silence/transition points"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument(
        "--broll", nargs="+", required=True, help="B-roll clip paths"
    )
    parser.add_argument(
        "--mode", default="silence", choices=["silence", "manual"],
        help="Detection mode (default: silence)",
    )
    parser.add_argument(
        "--max-insertions", type=int, default=5,
        help="Maximum B-roll insertions (default: 5)",
    )
    parser.add_argument(
        "--min-gap", type=float, default=2.0,
        help="Minimum silence gap in seconds (default: 2.0)",
    )

    args = parser.parse_args()

    skill = BRollInserter()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        broll_clips=[Path(p) for p in args.broll],
        mode=args.mode,
        max_insertions=args.max_insertions,
        min_gap=args.min_gap,
    )

    print(f"\n=== B-Roll Insertion Complete ===")
    print(f"Input:      {result['input_duration']:.1f}s")
    print(f"Output:     {result['output_duration']:.1f}s")
    print(f"Insertions: {result['insertions_count']}")
    for i, pt in enumerate(result["insertion_points"]):
        print(f"  [{i+1}] {pt['start']:.1f}s - {pt['end']:.1f}s ({pt['type']})")
