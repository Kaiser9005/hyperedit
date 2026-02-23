"""Skill 4: Chapter Generation.

Generates video chapters from transcription using silence detection
and topic signal analysis. Outputs JSON and/or YouTube timestamp format.
"""

import argparse
import json
import sys
from pathlib import Path

from whisper_service import WhisperService
from ffmpeg_service import FFmpegService


# Topic change signal words by language.
# When these appear near a silence boundary, the silence scores higher
# as a chapter break point.
TOPIC_SIGNALS = {
    "en": [
        "now", "next", "let's", "moving on", "so", "first", "second",
        "third", "finally", "another", "also", "okay", "alright",
        "let me", "the next", "in this", "welcome", "introduction",
        "conclusion", "summary", "step", "part", "section", "chapter",
    ],
    "fr": [
        "maintenant", "ensuite", "passons", "premierement", "deuxiemement",
        "troisiemement", "enfin", "aussi", "alors", "bon",
        "voyons", "regardons", "la suite", "bienvenue", "introduction",
        "conclusion", "resume", "etape", "partie", "section", "chapitre",
    ],
}


class ChapterGenerator:
    """Generate video chapters from transcription + silence analysis."""

    def __init__(self):
        self.whisper = WhisperService()
        self.ffmpeg = FFmpegService()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        min_chapter_duration: float = 30,
        max_chapters: int = 20,
        output_format: str = "both",
        language: str = "auto",
    ) -> dict:
        """
        Full V-I-V cycle for chapter generation.

        Args:
            input_path: Path to input video file.
            output_path: Base path for output files (no extension).
            min_chapter_duration: Minimum seconds per chapter.
            max_chapters: Maximum number of chapters to generate.
            output_format: 'json', 'youtube', or 'both'.
            language: Language for transcription and topic signals.

        Returns:
            dict with: chapters, total_duration, chapter_count, output_files
        """
        # === VERIFY (Before) ===
        meta = self.ffmpeg.get_metadata(input_path)
        if not meta.has_audio:
            raise ValueError(f"Input video has no audio track: {input_path}")
        total_duration = meta.duration

        # === IMPLEMENT ===
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Extract audio
        audio_path = work_dir / f"{input_path.stem}_audio.wav"
        self.whisper.extract_audio(input_path, audio_path)

        # 2. Transcribe
        transcription = self.whisper.transcribe(audio_path, language=language)
        segments = transcription.segments
        detected_language = transcription.language

        # 3. Detect silence (shorter threshold for chapter boundaries)
        silences = self.whisper.detect_silence(
            audio_path, noise_db=-35, min_duration=0.5
        )

        # 4. Find chapter boundaries
        boundaries = self._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=total_duration,
            min_duration=min_chapter_duration,
            max_chapters=max_chapters,
            language=detected_language if language == "auto" else language,
        )

        # 5. Generate chapters with titles
        chapters = self._generate_chapters(boundaries, segments, total_duration)

        # Cleanup temp audio
        if audio_path.exists():
            audio_path.unlink()

        # === VERIFY (After) ===
        # First chapter must start at 0:00
        if chapters and chapters[0]["start"] != 0.0:
            chapters[0]["start"] = 0.0

        # All chapters must have titles
        for i, ch in enumerate(chapters):
            if not ch.get("title"):
                ch["title"] = f"Chapter {i + 1}"

        # 6. Build and save result
        result = self._build_result(
            chapters, total_duration, output_path, output_format
        )

        return result

    def _find_chapter_boundaries(
        self,
        segments: list[dict],
        silences: list[dict],
        total_duration: float,
        min_duration: float,
        max_chapters: int,
        language: str,
    ) -> list[float]:
        """
        Score silences as potential chapter break points.

        Each silence gets a score based on:
        - Duration of the silence (longer = better break point)
        - Presence of topic signal words after the silence
        - Position relative to min_chapter_duration intervals

        Returns sorted list of boundary timestamps (excluding 0.0).
        """
        if not silences:
            return []

        lang_key = language.lower()[:2] if language else "en"
        signals = TOPIC_SIGNALS.get(lang_key, TOPIC_SIGNALS["en"])

        scored = []
        for silence in silences:
            silence_mid = (silence["start"] + silence["end"]) / 2
            silence_len = silence["end"] - silence["start"]

            # Skip silences too close to start or end
            if silence_mid < min_duration or silence_mid > total_duration - 5:
                continue

            # Base score from silence duration (0.5s=0.1, 2s=0.4, 5s+=1.0)
            score = min(silence_len / 5.0, 1.0)

            # Bonus for topic signal words in the segment after this silence
            for seg in segments:
                if seg["start"] >= silence["end"] and seg["start"] < silence["end"] + 3:
                    text_lower = seg["text"].lower()
                    for signal in signals:
                        if signal in text_lower:
                            score += 0.5
                            break
                    break  # Only check the first segment after silence

            scored.append((silence["end"], score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select boundaries respecting min_duration spacing
        boundaries = []
        for timestamp, _score in scored:
            if len(boundaries) >= max_chapters - 1:
                break

            # Check spacing from existing boundaries and from 0
            too_close = False
            check_points = [0.0] + boundaries
            for bp in check_points:
                if abs(timestamp - bp) < min_duration:
                    too_close = True
                    break

            if not too_close:
                boundaries.append(timestamp)

        boundaries.sort()
        return boundaries

    def _generate_chapters(
        self,
        boundaries: list[float],
        segments: list[dict],
        total_duration: float,
    ) -> list[dict]:
        """
        Create chapter dicts with title extracted from transcript.

        Each chapter has: start, end, title, duration.
        """
        if not boundaries:
            # Single chapter covering entire video
            title = self._extract_title(
                " ".join(s["text"] for s in segments[:3]) if segments else "",
                1,
            )
            return [
                {
                    "start": 0.0,
                    "end": total_duration,
                    "title": title,
                    "duration": total_duration,
                }
            ]

        # Build chapter list: [0, b1, b2, ..., total_duration]
        starts = [0.0] + boundaries
        ends = boundaries + [total_duration]

        chapters = []
        for i, (start, end) in enumerate(zip(starts, ends)):
            # Find segments that fall within this chapter
            chapter_segments = [
                s for s in segments if s["start"] >= start and s["start"] < end
            ]
            chapter_text = " ".join(s["text"] for s in chapter_segments[:5])

            title = self._extract_title(chapter_text, i + 1)

            chapters.append(
                {
                    "start": start,
                    "end": end,
                    "title": title,
                    "duration": round(end - start, 2),
                }
            )

        return chapters

    def _extract_title(self, text: str, chapter_num: int) -> str:
        """
        Extract chapter title from transcript text.

        Takes the first 8 words, capitalizes the first letter.
        Falls back to 'Chapter N' if text is empty.
        """
        text = text.strip()
        if not text:
            return f"Chapter {chapter_num}"

        words = text.split()[:8]
        title = " ".join(words)

        # Clean up and capitalize
        title = title.strip(".,;:!?-")
        if title:
            title = title[0].upper() + title[1:]

        return title if title else f"Chapter {chapter_num}"

    def _build_result(
        self,
        chapters: list[dict],
        total_duration: float,
        output_path: Path,
        output_format: str,
    ) -> dict:
        """
        Save chapters to file(s) and return result dict.

        Args:
            chapters: List of chapter dicts.
            total_duration: Total video duration in seconds.
            output_path: Base path (no extension).
            output_format: 'json', 'youtube', or 'both'.

        Returns:
            dict with chapters, total_duration, chapter_count, output_files
        """
        output_files = []

        if output_format in ("json", "both"):
            json_path = Path(str(output_path) + ".json")
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(
                    {
                        "chapters": chapters,
                        "total_duration": total_duration,
                        "chapter_count": len(chapters),
                    },
                    f,
                    indent=2,
                )
            output_files.append(str(json_path))

        if output_format in ("youtube", "both"):
            yt_path = Path(str(output_path) + "_youtube.txt")
            yt_path.parent.mkdir(parents=True, exist_ok=True)
            yt_text = self._format_youtube_chapters(chapters)
            with open(yt_path, "w") as f:
                f.write(yt_text)
            output_files.append(str(yt_path))

        return {
            "chapters": chapters,
            "total_duration": total_duration,
            "chapter_count": len(chapters),
            "output_files": output_files,
        }

    def _format_youtube_chapters(self, chapters: list[dict]) -> str:
        """
        Format chapters as YouTube description timestamps.

        Example output:
            0:00 Introduction
            1:30 Getting Started
            5:45 Advanced Topics
        """
        lines = []
        for ch in chapters:
            ts = self._seconds_to_timestamp(ch["start"])
            lines.append(f"{ts} {ch['title']}")
        return "\n".join(lines)

    @staticmethod
    def _seconds_to_timestamp(seconds: float) -> str:
        """
        Convert seconds to MM:SS or H:MM:SS format.

        Examples:
            0     -> '0:00'
            65    -> '1:05'
            3661  -> '1:01:01'
        """
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60

        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate video chapters")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument(
        "--output", required=True, help="Output base path (no extension)"
    )
    parser.add_argument(
        "--min-duration", type=float, default=30, help="Min chapter duration (seconds)"
    )
    parser.add_argument(
        "--max-chapters", type=int, default=20, help="Max number of chapters"
    )
    parser.add_argument(
        "--format",
        choices=["json", "youtube", "both"],
        default="both",
        help="Output format",
    )
    parser.add_argument("--language", default="auto", help="Transcription language")

    args = parser.parse_args()

    skill = ChapterGenerator()
    result = skill.execute(
        input_path=Path(args.input),
        output_path=Path(args.output),
        min_chapter_duration=args.min_duration,
        max_chapters=args.max_chapters,
        output_format=args.format,
        language=args.language,
    )

    print(f"\n=== Chapter Generation Complete ===")
    print(f"Duration: {result['total_duration']:.1f}s")
    print(f"Chapters: {result['chapter_count']}")
    print(f"Output files: {', '.join(result['output_files'])}")
    print(f"\nChapters:")
    for ch in result["chapters"]:
        ts = ChapterGenerator._seconds_to_timestamp(ch["start"])
        print(f"  {ts} {ch['title']} ({ch['duration']:.0f}s)")
