"""Skill 1: Dead Air & Silence Removal.

Removes dead air, silence gaps, and filler words from video.
Uses whisper.cpp for transcription and FFmpeg for cutting.
"""

import argparse
import shutil
import sys
from pathlib import Path

from whisper_service import WhisperService
from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance, QAResult


class DeadAirRemoval:
    """Remove silence and filler words from video."""

    def __init__(self):
        self.whisper = WhisperService()
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        silence_threshold_db: float = -40,
        min_silence_duration: float = 1.5,
        remove_fillers: bool = True,
        language: str = "auto",
    ) -> dict:
        """
        Full V-I-V cycle for dead air removal.

        Returns dict with: input_duration, output_duration, segments_removed,
                          filler_words_removed, qa_results
        """
        # === VERIFY (Before) ===
        meta = self.ffmpeg.get_metadata(input_path)
        if not meta.has_audio:
            raise ValueError(f"Input video has no audio track: {input_path}")
        input_duration = meta.duration

        # === IMPLEMENT ===
        work_dir = output_path.parent

        # 1. Extract audio
        audio_path = work_dir / f"{input_path.stem}_audio.wav"
        self.whisper.extract_audio(input_path, audio_path)

        # 2. Detect silence
        silences = self.whisper.detect_silence(
            audio_path,
            noise_db=silence_threshold_db,
            min_duration=min_silence_duration,
        )

        # 3. Detect filler words (if enabled)
        filler_segments = []
        if remove_fillers:
            transcription = self.whisper.transcribe(audio_path, language=language)
            filler_segments = self.whisper.detect_filler_words(transcription)

        # 4. Build removal list (merge silences + fillers)
        removals = []
        for s in silences:
            removals.append({"start": s["start"], "end": s["end"], "type": "silence"})
        for f in filler_segments:
            removals.append({"start": f["start"], "end": f["end"], "type": "filler"})

        # Sort by start time and merge overlapping
        removals.sort(key=lambda x: x["start"])
        merged = self._merge_overlapping(removals)

        if not merged:
            # Nothing to remove — copy input to output
            shutil.copy2(input_path, output_path)
            return {
                "input_duration": input_duration,
                "output_duration": input_duration,
                "segments_removed": 0,
                "filler_words_removed": 0,
                "time_saved": 0.0,
                "qa_results": [],
            }

        # 5. Build keep list (inverse of removal list)
        keeps = self._invert_segments(merged, input_duration)

        # 6. Extract and concatenate kept segments
        temp_clips = []
        for i, keep in enumerate(keeps):
            clip_path = work_dir / f"_keep_{i:04d}.mp4"
            self.ffmpeg.cut(input_path, clip_path, start=keep["start"], end=keep["end"])
            temp_clips.append(clip_path)

        if len(temp_clips) == 1:
            shutil.move(str(temp_clips[0]), str(output_path))
        else:
            self.ffmpeg.concat(temp_clips, output_path)

        # Cleanup temp clips
        for clip in temp_clips:
            if clip.exists():
                clip.unlink()
        if audio_path.exists():
            audio_path.unlink()

        # === VERIFY (After) ===
        output_meta = self.ffmpeg.get_metadata(output_path)
        qa_results = self.qa.full_check(
            output_path,
            min_width=meta.width,
            min_height=meta.height,
        )

        return {
            "input_duration": input_duration,
            "output_duration": output_meta.duration,
            "segments_removed": len(merged),
            "filler_words_removed": len(filler_segments),
            "time_saved": input_duration - output_meta.duration,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def _merge_overlapping(self, segments: list[dict]) -> list[dict]:
        """Merge overlapping time segments."""
        if not segments:
            return []

        merged = [segments[0].copy()]
        for seg in segments[1:]:
            if seg["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
            else:
                merged.append(seg.copy())
        return merged

    def _invert_segments(
        self, removals: list[dict], total_duration: float
    ) -> list[dict]:
        """Convert removal list to keep list."""
        keeps = []
        current = 0.0

        for removal in removals:
            if removal["start"] > current:
                keeps.append({"start": current, "end": removal["start"]})
            current = removal["end"]

        if current < total_duration:
            keeps.append({"start": current, "end": total_duration})

        return keeps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove dead air from video")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--silence-db", type=float, default=-40)
    parser.add_argument("--min-silence", type=float, default=1.5)
    parser.add_argument("--no-fillers", action="store_true")
    parser.add_argument("--language", default="auto")

    args = parser.parse_args()

    skill = DeadAirRemoval()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        silence_threshold_db=args.silence_db,
        min_silence_duration=args.min_silence,
        remove_fillers=not args.no_fillers,
        language=args.language,
    )

    print(f"\n=== Dead Air Removal Complete ===")
    print(f"Input:  {result['input_duration']:.1f}s")
    print(f"Output: {result['output_duration']:.1f}s")
    print(f"Saved:  {result['time_saved']:.1f}s")
    print(f"Segments removed: {result['segments_removed']}")
    print(f"Filler words removed: {result['filler_words_removed']}")
