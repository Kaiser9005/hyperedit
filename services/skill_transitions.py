"""Skill 3: Transitions.

Add transitions between video segments using FFmpeg fade and xfade filters.
Supports fade in/out on single videos and crossfade/dissolve/wipe/slide between clips.
"""

import argparse
import subprocess
from pathlib import Path

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class TransitionManager:
    """Apply transitions to video files: fade in/out, crossfade, dissolve, wipes, slides."""

    TRANSITIONS = {
        "fade": {"filter": "fade=t=out:st={end_offset}:d={duration}"},
        "crossfade": {"filter": "xfade=transition=fade:duration={duration}:offset={offset}"},
        "dissolve": {"filter": "xfade=transition=dissolve:duration={duration}:offset={offset}"},
        "wipeleft": {"filter": "xfade=transition=wipeleft:duration={duration}:offset={offset}"},
        "wiperight": {"filter": "xfade=transition=wiperight:duration={duration}:offset={offset}"},
        "slideup": {"filter": "xfade=transition=slideup:duration={duration}:offset={offset}"},
        "slidedown": {"filter": "xfade=transition=slidedown:duration={duration}:offset={offset}"},
        "circleopen": {"filter": "xfade=transition=circleopen:duration={duration}:offset={offset}"},
    }

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        transition_type: str = "fade",
        duration: float = 1.0,
        position: str = "end",
    ) -> dict:
        """Full V-I-V cycle for applying fade transitions to a single video.

        Args:
            input_path: Source video file.
            output_path: Destination for transitioned video.
            transition_type: Transition type (only "fade" applies to single video).
            duration: Fade duration in seconds.
            position: Where to apply fade: "start", "end", or "both".

        Returns:
            dict with input/output durations, transition details, and QA results.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        if transition_type not in self.TRANSITIONS:
            raise ValueError(
                f"Unknown transition '{transition_type}'. "
                f"Available: {list(self.TRANSITIONS.keys())}"
            )

        if position not in ("start", "end", "both"):
            raise ValueError(
                f"Invalid position '{position}'. Must be 'start', 'end', or 'both'."
            )

        meta = self.ffmpeg.get_metadata(input_path)
        input_duration = meta.duration

        if duration > input_duration / 2:
            raise ValueError(
                f"Fade duration {duration}s is too long for a {input_duration:.1f}s video."
            )

        # === IMPLEMENT ===
        fade_in = duration if position in ("start", "both") else 0.0
        fade_out = duration if position in ("end", "both") else 0.0
        self._apply_fade(input_path, output_path, fade_in, fade_out)

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"Output file was not created: {output_path}")

        out_meta = self.ffmpeg.get_metadata(output_path)
        output_duration = out_meta.duration

        # Duration should be preserved (fade does not change length)
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
            "transition_type": transition_type,
            "duration": duration,
            "position": position,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def apply_between_clips(
        self,
        clip_paths: list[Path],
        output_path: Path,
        transition_type: str = "crossfade",
        duration: float = 1.0,
    ) -> dict:
        """Apply xfade transitions between multiple clips and concatenate them.

        Each xfade reduces total duration by `duration` seconds per transition.

        Args:
            clip_paths: List of video file paths to join with transitions.
            output_path: Destination for the combined video.
            transition_type: Type of xfade transition.
            duration: Transition duration in seconds.

        Returns:
            dict with clip count, expected/actual duration, transition details, QA results.
        """
        clip_paths = [Path(p) for p in clip_paths]
        output_path = Path(output_path)

        if len(clip_paths) < 2:
            raise ValueError("Need at least 2 clips for between-clip transitions.")

        if transition_type not in self.TRANSITIONS:
            raise ValueError(
                f"Unknown transition '{transition_type}'. "
                f"Available: {list(self.TRANSITIONS.keys())}"
            )

        # === VERIFY (Before) ===
        clip_durations = []
        first_meta = None
        for i, clip in enumerate(clip_paths):
            if not clip.exists():
                raise FileNotFoundError(f"Clip not found: {clip}")
            meta = self.ffmpeg.get_metadata(clip)
            clip_durations.append(meta.duration)
            if i == 0:
                first_meta = meta

        # Each transition overlaps `duration` seconds
        num_transitions = len(clip_paths) - 1
        expected_duration = sum(clip_durations) - (num_transitions * duration)

        # === IMPLEMENT ===
        # Build xfade filter chain for N clips
        # For 2 clips: [0:v][1:v]xfade=...[v]
        # For 3 clips: [0:v][1:v]xfade=...[v01]; [v01][2:v]xfade=...[v]
        # Audio: acrossfade between audio streams

        inputs = []
        for clip in clip_paths:
            inputs.extend(["-i", str(clip)])

        filter_parts = []
        audio_filter_parts = []
        running_offset = clip_durations[0] - duration

        for i in range(num_transitions):
            # Determine xfade transition name for filter
            if transition_type == "fade":
                xfade_name = "fade"
            elif transition_type == "crossfade":
                xfade_name = "fade"
            else:
                xfade_name = transition_type

            # Video xfade
            if i == 0:
                src_label = f"[0:v]"
            else:
                src_label = f"[v{i - 1}]"

            dst_label = f"[{i + 1}:v]"

            if i == num_transitions - 1:
                out_label = "[v]"
            else:
                out_label = f"[v{i}]"

            filter_parts.append(
                f"{src_label}{dst_label}xfade=transition={xfade_name}"
                f":duration={duration}:offset={running_offset}{out_label}"
            )

            # Audio crossfade
            if i == 0:
                a_src = f"[0:a]"
            else:
                a_src = f"[a{i - 1}]"

            a_dst = f"[{i + 1}:a]"

            if i == num_transitions - 1:
                a_out = "[a]"
            else:
                a_out = f"[a{i}]"

            audio_filter_parts.append(
                f"{a_src}{a_dst}acrossfade=d={duration}:c1=tri:c2=tri{a_out}"
            )

            # Update offset for next transition
            if i + 1 < num_transitions:
                running_offset += clip_durations[i + 1] - duration

        filter_complex = ";".join(filter_parts + audio_filter_parts)

        cmd = [
            self.ffmpeg.ffmpeg,
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # === VERIFY (After) ===
        if not output_path.exists():
            raise RuntimeError(f"Output file was not created: {output_path}")

        out_meta = self.ffmpeg.get_metadata(output_path)

        # Duration tolerance: 1.0s for multi-clip xfade operations
        if abs(out_meta.duration - expected_duration) > 1.0:
            raise RuntimeError(
                f"Duration mismatch: expected ~{expected_duration:.2f}s "
                f"but got {out_meta.duration:.2f}s"
            )

        qa_results = self.qa.full_check(
            output_path,
            expected_duration=expected_duration,
            min_width=first_meta.width,
            min_height=first_meta.height,
        )

        return {
            "clip_count": len(clip_paths),
            "clip_durations": clip_durations,
            "expected_duration": expected_duration,
            "output_duration": out_meta.duration,
            "transition_type": transition_type,
            "duration": duration,
            "num_transitions": num_transitions,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def list_transitions(self) -> list[str]:
        """Return available transition type names."""
        return list(self.TRANSITIONS.keys())

    def _apply_fade(
        self,
        input_path: Path,
        output_path: Path,
        fade_in_duration: float,
        fade_out_duration: float,
    ) -> Path:
        """Apply fade in/out filters to a single video.

        Args:
            input_path: Source video.
            output_path: Destination video.
            fade_in_duration: Fade-in duration (0 to skip).
            fade_out_duration: Fade-out duration (0 to skip).

        Returns:
            Path to the output video.
        """
        meta = self.ffmpeg.get_metadata(input_path)
        video_duration = meta.duration

        filters = []
        if fade_in_duration > 0:
            filters.append(f"fade=t=in:st=0:d={fade_in_duration}")
        if fade_out_duration > 0:
            fade_out_start = video_duration - fade_out_duration
            filters.append(f"fade=t=out:st={fade_out_start}:d={fade_out_duration}")

        if not filters:
            raise ValueError("At least one of fade_in or fade_out must be > 0")

        vf = ",".join(filters)

        # Build audio fade filters to match video fades
        audio_filters = []
        if fade_in_duration > 0:
            audio_filters.append(f"afade=t=in:st=0:d={fade_in_duration}")
        if fade_out_duration > 0:
            fade_out_start = video_duration - fade_out_duration
            audio_filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out_duration}")

        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", vf,
        ]

        if audio_filters and meta.has_audio:
            af = ",".join(audio_filters)
            cmd.extend(["-af", af])
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "copy"])

        cmd.extend([str(output_path), "-y"])
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add transitions to video")
    parser.add_argument("--input", default=None, help="Input video path (single-video fade)")
    parser.add_argument("--clips", nargs="+", default=None, help="Multiple clip paths (xfade)")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--type", default="fade", help="Transition type")
    parser.add_argument("--duration", type=float, default=1.0, help="Transition duration (seconds)")
    parser.add_argument("--position", default="end", help="Fade position: start, end, both")

    args = parser.parse_args()

    skill = TransitionManager()

    if args.clips:
        result = skill.apply_between_clips(
            clip_paths=[Path(c) for c in args.clips],
            output_path=Path(args.output),
            transition_type=args.type,
            duration=args.duration,
        )
        print("\n=== Multi-Clip Transition Complete ===")
        print(f"Clips: {result['clip_count']}")
        print(f"Transition: {result['transition_type']} ({result['duration']}s)")
        print(f"Duration: {result['expected_duration']:.1f}s expected -> {result['output_duration']:.1f}s actual")
    elif args.input:
        result = skill.execute(
            input_path=Path(args.input),
            output_path=Path(args.output),
            transition_type=args.type,
            duration=args.duration,
            position=args.position,
        )
        print("\n=== Fade Transition Complete ===")
        print(f"Transition: {result['transition_type']} (position={result['position']}, {result['duration']}s)")
        print(f"Duration: {result['input_duration']:.1f}s -> {result['output_duration']:.1f}s")
    else:
        parser.error("Either --input or --clips must be provided")

    qa = result.get("qa_results", [])
    print(f"QA: {sum(1 for r in qa if r['passed'])}/{len(qa)} checks passed")
