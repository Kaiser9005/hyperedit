"""Tests for Skill 4: Chapter Generation.

Tests helper methods only — no whisper.cpp or FFmpeg required.
"""

import json
import tempfile
from pathlib import Path

import pytest

from skill_chapters import ChapterGenerator, TOPIC_SIGNALS


@pytest.fixture
def gen():
    """ChapterGenerator instance (no external deps needed for helper tests)."""
    return ChapterGenerator()


# --- _seconds_to_timestamp ---


class TestSecondsToTimestamp:
    def test_zero(self):
        assert ChapterGenerator._seconds_to_timestamp(0) == "0:00"

    def test_65_seconds(self):
        assert ChapterGenerator._seconds_to_timestamp(65) == "1:05"

    def test_3661_seconds(self):
        assert ChapterGenerator._seconds_to_timestamp(3661) == "1:01:01"

    def test_exact_minute(self):
        assert ChapterGenerator._seconds_to_timestamp(120) == "2:00"

    def test_exact_hour(self):
        assert ChapterGenerator._seconds_to_timestamp(3600) == "1:00:00"

    def test_float_truncates(self):
        assert ChapterGenerator._seconds_to_timestamp(65.9) == "1:05"


# --- _extract_title ---


class TestExtractTitle:
    def test_normal_text(self, gen):
        title = gen._extract_title("hello world this is a test video recording session", 1)
        assert title == "Hello world this is a test video recording"

    def test_short_text(self, gen):
        title = gen._extract_title("hello world", 1)
        assert title == "Hello world"

    def test_empty_text(self, gen):
        title = gen._extract_title("", 1)
        assert title == "Chapter 1"

    def test_whitespace_only(self, gen):
        title = gen._extract_title("   ", 3)
        assert title == "Chapter 3"

    def test_capitalizes_first_letter(self, gen):
        title = gen._extract_title("lower case start", 1)
        assert title[0] == "L"

    def test_strips_punctuation(self, gen):
        title = gen._extract_title("...hello world", 1)
        assert not title.startswith(".")


# --- _format_youtube_chapters ---


class TestFormatYoutubeChapters:
    def test_basic_format(self, gen):
        chapters = [
            {"start": 0.0, "title": "Introduction"},
            {"start": 90.0, "title": "Getting Started"},
            {"start": 345.0, "title": "Advanced Topics"},
        ]
        result = gen._format_youtube_chapters(chapters)
        lines = result.split("\n")
        assert lines[0] == "0:00 Introduction"
        assert lines[1] == "1:30 Getting Started"
        assert lines[2] == "5:45 Advanced Topics"

    def test_single_chapter(self, gen):
        chapters = [{"start": 0.0, "title": "Full Video"}]
        result = gen._format_youtube_chapters(chapters)
        assert result == "0:00 Full Video"

    def test_hour_long_timestamps(self, gen):
        chapters = [
            {"start": 0.0, "title": "Start"},
            {"start": 3661.0, "title": "Hour Mark"},
        ]
        result = gen._format_youtube_chapters(chapters)
        lines = result.split("\n")
        assert lines[1] == "1:01:01 Hour Mark"


# --- _find_chapter_boundaries ---


class TestFindChapterBoundaries:
    def test_basic_boundaries(self, gen):
        segments = [
            {"start": 0, "end": 5, "text": "Hello introduction"},
            {"start": 31, "end": 35, "text": "Now let's move on"},
            {"start": 62, "end": 66, "text": "Next topic here"},
        ]
        silences = [
            {"start": 29, "end": 31},
            {"start": 60, "end": 62},
        ]
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=120,
            min_duration=30,
            max_chapters=10,
            language="en",
        )
        assert len(boundaries) >= 1
        assert all(b > 0 for b in boundaries)
        assert boundaries == sorted(boundaries)

    def test_no_silences(self, gen):
        segments = [{"start": 0, "end": 60, "text": "continuous talk"}]
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=[],
            total_duration=120,
            min_duration=30,
            max_chapters=10,
            language="en",
        )
        assert boundaries == []

    def test_respects_max_chapters(self, gen):
        silences = [{"start": i * 10, "end": i * 10 + 1} for i in range(3, 20)]
        segments = [
            {"start": s["end"], "end": s["end"] + 5, "text": "Some text"}
            for s in silences
        ]
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=300,
            min_duration=10,
            max_chapters=3,
            language="en",
        )
        # max_chapters=3 means at most 2 boundaries (boundary count = chapters - 1)
        assert len(boundaries) <= 2

    def test_respects_min_duration(self, gen):
        silences = [
            {"start": 10, "end": 11},
            {"start": 15, "end": 16},
        ]
        segments = []
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=120,
            min_duration=30,
            max_chapters=10,
            language="en",
        )
        # Both silences are within 30s of start; at most one can be selected,
        # and even that one must be >=30s from 0.0
        assert len(boundaries) <= 1
        for b in boundaries:
            assert b >= 30

    def test_topic_signal_boost(self, gen):
        """Silences followed by topic signal words should score higher."""
        segments = [
            {"start": 0, "end": 5, "text": "Regular text here"},
            {"start": 61, "end": 65, "text": "More regular text"},
            {"start": 121, "end": 125, "text": "Now let's discuss"},
        ]
        silences = [
            {"start": 59, "end": 61},   # No signal after
            {"start": 119, "end": 121},  # "Now" is a signal word
        ]
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=180,
            min_duration=30,
            max_chapters=2,
            language="en",
        )
        # With max 1 boundary, the one with the topic signal should be preferred
        if len(boundaries) == 1:
            assert boundaries[0] == 121

    def test_french_signals(self, gen):
        segments = [
            {"start": 61, "end": 65, "text": "Maintenant voyons la suite"},
        ]
        silences = [
            {"start": 59, "end": 61},
        ]
        boundaries = gen._find_chapter_boundaries(
            segments=segments,
            silences=silences,
            total_duration=180,
            min_duration=30,
            max_chapters=10,
            language="fr",
        )
        assert len(boundaries) >= 1


# --- _build_result ---


class TestBuildResult:
    def test_json_output(self, gen):
        chapters = [
            {"start": 0.0, "end": 60.0, "title": "Intro", "duration": 60.0},
            {"start": 60.0, "end": 120.0, "title": "Main", "duration": 60.0},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapters"
            result = gen._build_result(chapters, 120.0, output_path, "json")

            assert result["chapter_count"] == 2
            assert result["total_duration"] == 120.0
            assert len(result["output_files"]) == 1
            assert result["output_files"][0].endswith(".json")

            # Verify JSON file contents
            with open(result["output_files"][0]) as f:
                data = json.load(f)
            assert data["chapter_count"] == 2
            assert len(data["chapters"]) == 2
            assert data["chapters"][0]["title"] == "Intro"

    def test_youtube_output(self, gen):
        chapters = [
            {"start": 0.0, "end": 90.0, "title": "Start", "duration": 90.0},
            {"start": 90.0, "end": 180.0, "title": "Middle", "duration": 90.0},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapters"
            result = gen._build_result(chapters, 180.0, output_path, "youtube")

            assert len(result["output_files"]) == 1
            assert result["output_files"][0].endswith("_youtube.txt")

            # Verify YouTube text contents
            with open(result["output_files"][0]) as f:
                content = f.read()
            assert "0:00 Start" in content
            assert "1:30 Middle" in content

    def test_both_output(self, gen):
        chapters = [
            {"start": 0.0, "end": 120.0, "title": "Full", "duration": 120.0},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapters"
            result = gen._build_result(chapters, 120.0, output_path, "both")

            assert len(result["output_files"]) == 2
            extensions = {Path(f).suffix for f in result["output_files"]}
            assert ".json" in extensions
            assert ".txt" in extensions


# --- _generate_chapters ---


class TestGenerateChapters:
    def test_no_boundaries(self, gen):
        segments = [
            {"start": 0, "end": 10, "text": "Hello world today"},
        ]
        chapters = gen._generate_chapters([], segments, 120.0)
        assert len(chapters) == 1
        assert chapters[0]["start"] == 0.0
        assert chapters[0]["end"] == 120.0
        assert chapters[0]["title"] != ""

    def test_single_boundary(self, gen):
        segments = [
            {"start": 0, "end": 5, "text": "Introduction to the topic"},
            {"start": 60, "end": 65, "text": "Second section begins here"},
        ]
        chapters = gen._generate_chapters([60.0], segments, 120.0)
        assert len(chapters) == 2
        assert chapters[0]["start"] == 0.0
        assert chapters[0]["end"] == 60.0
        assert chapters[1]["start"] == 60.0
        assert chapters[1]["end"] == 120.0

    def test_multiple_boundaries(self, gen):
        segments = [
            {"start": 0, "end": 5, "text": "Part one content"},
            {"start": 60, "end": 65, "text": "Part two content"},
            {"start": 120, "end": 125, "text": "Part three content"},
        ]
        chapters = gen._generate_chapters([60.0, 120.0], segments, 180.0)
        assert len(chapters) == 3
        assert chapters[0]["start"] == 0.0
        assert chapters[1]["start"] == 60.0
        assert chapters[2]["start"] == 120.0
        assert chapters[2]["end"] == 180.0

    def test_chapter_durations(self, gen):
        chapters = gen._generate_chapters([30.0, 90.0], [], 120.0)
        assert chapters[0]["duration"] == 30.0
        assert chapters[1]["duration"] == 60.0
        assert chapters[2]["duration"] == 30.0

    def test_empty_segments_fallback_title(self, gen):
        chapters = gen._generate_chapters([60.0], [], 120.0)
        assert len(chapters) == 2
        # With no segments, titles should fall back to "Chapter N"
        assert "Chapter" in chapters[0]["title"]
        assert "Chapter" in chapters[1]["title"]


# --- TOPIC_SIGNALS ---


class TestTopicSignals:
    def test_en_signals_exist(self):
        assert "en" in TOPIC_SIGNALS
        assert len(TOPIC_SIGNALS["en"]) > 0

    def test_fr_signals_exist(self):
        assert "fr" in TOPIC_SIGNALS
        assert len(TOPIC_SIGNALS["fr"]) > 0

    def test_all_signals_lowercase(self):
        for lang, signals in TOPIC_SIGNALS.items():
            for signal in signals:
                assert signal == signal.lower(), f"{lang}: '{signal}' is not lowercase"
