"""Skill 10: Short-Form Clip Extraction.

Extracts short-form clips (TikTok, Reels, Shorts) from longer videos.
Uses whisper.cpp for transcription-based segment scoring and FFmpeg for
cutting and cropping.
"""

import argparse
from pathlib import Path

from whisper_service import WhisperService
from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class ShortFormExtractor:
    """Extract short-form clips from longer videos."""

    FORMAT_PRESETS = {
        "tiktok": {"max_duration": 60, "aspect": "9:16", "resolution": "1080x1920"},
        "reels": {"max_duration": 90, "aspect": "9:16", "resolution": "1080x1920"},
        "shorts": {"max_duration": 60, "aspect": "9:16", "resolution": "1080x1920"},
        "square": {"max_duration": 60, "aspect": "1:1", "resolution": "1080x1080"},
        "landscape": {"max_duration": 120, "aspect": "16:9", "resolution": "1920x1080"},
    }

    def __init__(self):
        self.whisper = WhisperService()
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_dir: Path,
        format_preset: str = "shorts",
        max_clips: int = 5,
        min_clip_duration: float = 10,
        max_clip_duration: float = 60,
        language: str = "auto",
    ) -> dict:
        """
        Full V-I-V cycle for short-form clip extraction.

        Returns dict with: clips_created, clips (list of clip info), format
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        if format_preset not in self.FORMAT_PRESETS:
            raise ValueError(
                f"Unknown format preset '{format_preset}'. "
                f"Available: {list(self.FORMAT_PRESETS.keys())}"
            )

        preset = self.FORMAT_PRESETS[format_preset]

        # Cap max_clip_duration to the preset limit
        max_clip_duration = min(max_clip_duration, preset["max_duration"])

        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        if not meta.has_audio:
            raise ValueError(f"Input video has no audio track: {input_path}")

        total_duration = meta.duration

        if total_duration < min_clip_duration:
            raise ValueError(
                f"Input video too short ({total_duration:.1f}s) "
                f"for minimum clip duration ({min_clip_duration}s)"
            )

        # === IMPLEMENT ===
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Extract audio and transcribe
        audio_path = output_dir / f"{input_path.stem}_audio.wav"
        self.whisper.extract_audio(input_path, audio_path)
        transcription = self.whisper.transcribe(audio_path, language=language)

        # 2. Detect silence gaps (natural break points)
        silences = self.whisper.detect_silence(
            audio_path, noise_db=-40, min_duration=0.5
        )

        # 3. Identify interesting segments
        candidates = self._find_interesting_segments(
            segments=transcription.segments,
            silences=silences,
            total_duration=total_duration,
            min_duration=min_clip_duration,
            max_duration=max_clip_duration,
            max_clips=max_clips,
        )

        # 4. Extract top N clips
        clips = []
        for i, candidate in enumerate(candidates):
            clip_filename = f"{input_path.stem}_clip_{i:02d}_{format_preset}.mp4"
            clip_path = output_dir / clip_filename
            self._extract_clip(
                input_path=input_path,
                output_path=clip_path,
                start=candidate["start"],
                end=candidate["end"],
                format_preset=format_preset,
            )
            clips.append(
                {
                    "path": str(clip_path),
                    "start": candidate["start"],
                    "end": candidate["end"],
                    "duration": candidate["end"] - candidate["start"],
                    "score": candidate.get("score", 0),
                }
            )

        # Cleanup temp audio
        if audio_path.exists():
            audio_path.unlink()

        # === VERIFY (After) ===
        verified_clips = []
        for clip_info in clips:
            clip_path = Path(clip_info["path"])
            if not clip_path.exists():
                continue
            clip_meta = self.ffmpeg.get_metadata(clip_path)
            if clip_meta.duration < min_clip_duration:
                continue
            if clip_meta.duration > max_clip_duration + 1.0:  # 1s tolerance
                continue
            verified_clips.append(clip_info)

        return {
            "clips_created": len(verified_clips),
            "clips": verified_clips,
            "format": format_preset,
        }

    def _find_interesting_segments(
        self,
        segments: list[dict],
        silences: list[dict],
        total_duration: float,
        min_duration: float,
        max_duration: float,
        max_clips: int,
    ) -> list[dict]:
        """
        Score segments by speech density and group into candidate clips.

        Speech density = words per second. Segments with more speech
        are considered more interesting/engaging for short-form content.

        Returns top-scored candidates sorted by score descending.
        """
        if not segments:
            return []

        # Build silence lookup for snapping clip boundaries
        silence_points = []
        for s in silences:
            silence_points.append(s["start"])
            silence_points.append(s["end"])
        silence_points.sort()

        # Group transcript segments into candidate clips
        candidates = []
        i = 0
        while i < len(segments):
            # Start a new candidate at this segment
            clip_start = segments[i]["start"]
            clip_end = segments[i]["end"]
            clip_words = len(segments[i].get("text", "").split())
            j = i + 1

            # Extend the candidate by adding consecutive segments
            while j < len(segments) and (clip_end - clip_start) < max_duration:
                next_seg = segments[j]
                potential_end = next_seg["end"]

                if (potential_end - clip_start) > max_duration:
                    break

                clip_end = potential_end
                clip_words += len(next_seg.get("text", "").split())
                j += 1

            clip_duration = clip_end - clip_start

            if clip_duration >= min_duration:
                # Snap boundaries to silence points if close (within 0.5s)
                snapped_start = self._snap_to_silence(
                    clip_start, silence_points, threshold=0.5, prefer="before"
                )
                snapped_end = self._snap_to_silence(
                    clip_end, silence_points, threshold=0.5, prefer="after"
                )

                # Ensure we don't go negative or beyond total duration
                snapped_start = max(0, snapped_start)
                snapped_end = min(total_duration, snapped_end)

                final_duration = snapped_end - snapped_start

                if min_duration <= final_duration <= max_duration:
                    words_per_second = clip_words / final_duration if final_duration > 0 else 0
                    candidates.append(
                        {
                            "start": round(snapped_start, 3),
                            "end": round(snapped_end, 3),
                            "duration": round(final_duration, 3),
                            "word_count": clip_words,
                            "score": round(words_per_second, 3),
                        }
                    )

            # Advance: skip forward by roughly half the segments we consumed
            # so candidates can overlap for better coverage
            step = max(1, (j - i) // 2)
            i += step

        # Remove overlapping candidates (keep higher scored)
        candidates.sort(key=lambda c: c["score"], reverse=True)
        selected = []
        for cand in candidates:
            if len(selected) >= max_clips:
                break
            # Check overlap with already selected
            overlaps = False
            for sel in selected:
                overlap_start = max(cand["start"], sel["start"])
                overlap_end = min(cand["end"], sel["end"])
                if overlap_end > overlap_start:
                    overlap_ratio = (overlap_end - overlap_start) / cand["duration"]
                    if overlap_ratio > 0.3:  # More than 30% overlap
                        overlaps = True
                        break
            if not overlaps:
                selected.append(cand)

        # Sort selected by start time for sequential output
        selected.sort(key=lambda c: c["start"])
        return selected

    def _snap_to_silence(
        self,
        time_point: float,
        silence_points: list[float],
        threshold: float = 0.5,
        prefer: str = "before",
    ) -> float:
        """Snap a time point to the nearest silence boundary if within threshold."""
        if not silence_points:
            return time_point

        best = time_point
        best_dist = threshold + 1  # Start beyond threshold

        for sp in silence_points:
            dist = abs(sp - time_point)
            if dist < best_dist:
                if prefer == "before" and sp <= time_point:
                    best = sp
                    best_dist = dist
                elif prefer == "after" and sp >= time_point:
                    best = sp
                    best_dist = dist
                elif dist < best_dist:
                    best = sp
                    best_dist = dist

        return best if best_dist <= threshold else time_point

    def _extract_clip(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
        format_preset: str,
    ) -> Path:
        """Cut a segment and optionally crop to target aspect ratio."""
        preset = self.FORMAT_PRESETS[format_preset]
        target_aspect = preset["aspect"]

        # Get source aspect ratio
        meta = self.ffmpeg.get_metadata(input_path)
        src_ratio = meta.width / meta.height

        # Parse target aspect ratio
        w_ratio, h_ratio = map(int, target_aspect.split(":"))
        target_ratio = w_ratio / h_ratio

        # Check if cropping is needed (tolerance of 5%)
        needs_crop = abs(src_ratio - target_ratio) / max(src_ratio, target_ratio) > 0.05

        if needs_crop:
            # Cut first (re-encode for reliable keyframes), then crop
            temp_cut = output_path.with_suffix(".tmp.mp4")
            self.ffmpeg.cut(input_path, temp_cut, start=start, end=end, reencode=True)
            self.ffmpeg.crop_aspect(temp_cut, output_path, aspect=target_aspect)
            if temp_cut.exists():
                temp_cut.unlink()
        else:
            # Re-encode to ensure reliable output (stream copy can lose
            # video on short clips if no keyframe falls within the range)
            self.ffmpeg.cut(input_path, output_path, start=start, end=end, reencode=True)

        return output_path

    def list_formats(self) -> dict:
        """Return all available format presets."""
        return dict(self.FORMAT_PRESETS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract short-form clips from video"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output-dir", required=True, help="Output directory for clips")
    parser.add_argument(
        "--format",
        default="shorts",
        choices=list(ShortFormExtractor.FORMAT_PRESETS.keys()),
        help="Format preset (default: shorts)",
    )
    parser.add_argument("--max-clips", type=int, default=5, help="Max clips to extract")
    parser.add_argument("--min-duration", type=float, default=10, help="Min clip duration (s)")
    parser.add_argument("--max-duration", type=float, default=60, help="Max clip duration (s)")
    parser.add_argument("--language", default="auto", help="Transcription language")

    args = parser.parse_args()

    extractor = ShortFormExtractor()
    result = extractor.execute(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        format_preset=args.format,
        max_clips=args.max_clips,
        min_clip_duration=args.min_duration,
        max_clip_duration=args.max_duration,
        language=args.language,
    )

    print(f"\n=== Short-Form Clip Extraction Complete ===")
    print(f"Format: {result['format']}")
    print(f"Clips created: {result['clips_created']}")
    for clip in result["clips"]:
        print(
            f"  - {Path(clip['path']).name}: "
            f"{clip['start']:.1f}s - {clip['end']:.1f}s "
            f"({clip['duration']:.1f}s, score={clip['score']:.2f})"
        )
