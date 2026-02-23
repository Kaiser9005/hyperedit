"""Tests for Skill 10: Short-Form Clip Extraction.

These tests do NOT require whisper.cpp — they test helper logic,
format presets, and FFmpeg-based operations with synthetic test video.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure services/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

from skill_shortform import ShortFormExtractor


@pytest.fixture
def extractor():
    """Create a ShortFormExtractor instance (no whisper/ffmpeg calls in most tests)."""
    return ShortFormExtractor()


@pytest.fixture
def test_video(tmp_path):
    """Generate a 10-second SMPTE bars test video with a sine tone."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=10" '
        f'-f lavfi -i "sine=frequency=440:duration=10" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    if not path.exists():
        pytest.skip("ffmpeg not available to generate test video")
    return path


# --- Format Preset Tests (no external dependencies) ---


class TestListFormats:
    def test_list_formats_returns_five_presets(self, extractor):
        formats = extractor.list_formats()
        assert len(formats) == 5

    def test_list_formats_contains_expected_keys(self, extractor):
        formats = extractor.list_formats()
        expected = {"tiktok", "reels", "shorts", "square", "landscape"}
        assert set(formats.keys()) == expected

    def test_list_formats_returns_dict_copy(self, extractor):
        """list_formats should not expose mutable internal state."""
        formats = extractor.list_formats()
        formats["custom"] = {"max_duration": 30}
        assert "custom" not in extractor.FORMAT_PRESETS


class TestFormatPresetValues:
    def test_tiktok_preset(self, extractor):
        preset = extractor.FORMAT_PRESETS["tiktok"]
        assert preset["max_duration"] == 60
        assert preset["aspect"] == "9:16"
        assert preset["resolution"] == "1080x1920"

    def test_reels_preset(self, extractor):
        preset = extractor.FORMAT_PRESETS["reels"]
        assert preset["max_duration"] == 90
        assert preset["aspect"] == "9:16"
        assert preset["resolution"] == "1080x1920"

    def test_shorts_preset(self, extractor):
        preset = extractor.FORMAT_PRESETS["shorts"]
        assert preset["max_duration"] == 60
        assert preset["aspect"] == "9:16"
        assert preset["resolution"] == "1080x1920"

    def test_square_preset(self, extractor):
        preset = extractor.FORMAT_PRESETS["square"]
        assert preset["max_duration"] == 60
        assert preset["aspect"] == "1:1"
        assert preset["resolution"] == "1080x1080"

    def test_landscape_preset(self, extractor):
        preset = extractor.FORMAT_PRESETS["landscape"]
        assert preset["max_duration"] == 120
        assert preset["aspect"] == "16:9"
        assert preset["resolution"] == "1920x1080"

    def test_all_presets_have_required_keys(self, extractor):
        for name, preset in extractor.FORMAT_PRESETS.items():
            assert "max_duration" in preset, f"{name} missing max_duration"
            assert "aspect" in preset, f"{name} missing aspect"
            assert "resolution" in preset, f"{name} missing resolution"


# --- Segment Scoring Tests (no external dependencies) ---


class TestFindInterestingSegments:
    def test_returns_empty_for_no_segments(self, extractor):
        result = extractor._find_interesting_segments(
            segments=[],
            silences=[],
            total_duration=60,
            min_duration=5,
            max_duration=30,
            max_clips=3,
        )
        assert result == []

    def test_scores_by_speech_density(self, extractor):
        """Segments with higher word density should score higher."""
        segments = [
            # Dense segment: 20 words in 5 seconds = 4 wps
            {"start": 0, "end": 5, "text": " ".join(["word"] * 20)},
            # Sparse segment: 5 words in 5 seconds = 1 wps
            {"start": 30, "end": 35, "text": " ".join(["word"] * 5)},
        ]
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=[],
            total_duration=60,
            min_duration=3,
            max_duration=10,
            max_clips=5,
        )
        # Both segments should be found
        assert len(result) >= 1
        # The dense segment should have a higher score
        if len(result) == 2:
            scores = {r["start"]: r["score"] for r in result}
            assert scores[0] > scores[30]

    def test_respects_max_clips_limit(self, extractor):
        """Should not return more than max_clips."""
        # Create many segments spread across a long video
        segments = []
        for i in range(20):
            start = i * 15
            segments.append(
                {"start": start, "end": start + 10, "text": "word " * 10}
            )
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=[],
            total_duration=300,
            min_duration=5,
            max_duration=15,
            max_clips=3,
        )
        assert len(result) <= 3

    def test_respects_min_duration(self, extractor):
        """Clips shorter than min_duration should be excluded."""
        segments = [
            {"start": 0, "end": 2, "text": "too short"},
            {"start": 10, "end": 25, "text": "long enough segment with words"},
        ]
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=[],
            total_duration=60,
            min_duration=10,
            max_duration=30,
            max_clips=5,
        )
        for clip in result:
            assert clip["duration"] >= 10

    def test_respects_max_duration(self, extractor):
        """Clips should not exceed max_duration."""
        segments = [
            {"start": 0, "end": 5, "text": "word " * 10},
            {"start": 5, "end": 10, "text": "word " * 10},
            {"start": 10, "end": 15, "text": "word " * 10},
            {"start": 15, "end": 20, "text": "word " * 10},
        ]
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=[],
            total_duration=60,
            min_duration=5,
            max_duration=12,
            max_clips=5,
        )
        for clip in result:
            assert clip["duration"] <= 12

    def test_avoids_excessive_overlap(self, extractor):
        """Selected clips should not have >30% overlap."""
        segments = [
            {"start": 0, "end": 5, "text": "word " * 15},
            {"start": 5, "end": 10, "text": "word " * 15},
            {"start": 10, "end": 15, "text": "word " * 15},
            {"start": 15, "end": 20, "text": "word " * 15},
            {"start": 20, "end": 25, "text": "word " * 15},
            {"start": 25, "end": 30, "text": "word " * 15},
        ]
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=[],
            total_duration=60,
            min_duration=5,
            max_duration=20,
            max_clips=5,
        )
        # Check no pair has >30% overlap
        for i, a in enumerate(result):
            for j, b in enumerate(result):
                if i >= j:
                    continue
                overlap_start = max(a["start"], b["start"])
                overlap_end = min(a["end"], b["end"])
                if overlap_end > overlap_start:
                    shorter = min(a["duration"], b["duration"])
                    overlap_ratio = (overlap_end - overlap_start) / shorter
                    assert overlap_ratio <= 0.31, (
                        f"Clips {i} and {j} overlap {overlap_ratio:.0%}"
                    )

    def test_snaps_to_silence_points(self, extractor):
        """Clip boundaries should snap to nearby silence points."""
        segments = [
            {"start": 1.0, "end": 6.0, "text": "word " * 15},
            {"start": 6.0, "end": 12.0, "text": "word " * 15},
        ]
        silences = [
            {"start": 0.8, "end": 1.2},   # Silence near segment start
            {"start": 11.8, "end": 12.5},  # Silence near segment end
        ]
        result = extractor._find_interesting_segments(
            segments=segments,
            silences=silences,
            total_duration=60,
            min_duration=5,
            max_duration=15,
            max_clips=5,
        )
        if result:
            # The first clip start should snap to silence boundary
            clip = result[0]
            assert clip["start"] <= 1.2


# --- FFmpeg-Based Tests (require ffmpeg) ---


class TestExtractClip:
    def test_extract_clip_creates_output(self, extractor, test_video, tmp_path):
        """Cutting a segment should produce a valid output file."""
        output = tmp_path / "clip.mp4"
        extractor._extract_clip(
            input_path=test_video,
            output_path=output,
            start=1.0,
            end=5.0,
            format_preset="landscape",
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_extract_clip_duration(self, extractor, test_video, tmp_path):
        """Extracted clip duration should match requested range (within tolerance)."""
        output = tmp_path / "clip.mp4"
        extractor._extract_clip(
            input_path=test_video,
            output_path=output,
            start=2.0,
            end=7.0,
            format_preset="landscape",
        )
        meta = extractor.ffmpeg.get_metadata(output)
        # Duration should be approximately 5s (2s tolerance for codec alignment)
        assert 3.0 <= meta.duration <= 7.0


class TestExtractClipWithCrop:
    def test_crop_to_vertical(self, extractor, test_video, tmp_path):
        """Cropping 16:9 source to 9:16 should produce a tall video."""
        output = tmp_path / "clip_vertical.mp4"
        extractor._extract_clip(
            input_path=test_video,
            output_path=output,
            start=1.0,
            end=5.0,
            format_preset="tiktok",
        )
        assert output.exists()
        meta = extractor.ffmpeg.get_metadata(output)
        # For 9:16 crop from 1920x1080:
        # height stays 1080, width becomes 1080 * 9/16 = 607.5 -> 607 or 608
        assert meta.height >= meta.width, (
            f"Expected vertical video, got {meta.width}x{meta.height}"
        )

    def test_crop_to_square(self, extractor, test_video, tmp_path):
        """Cropping to 1:1 should produce a square video."""
        output = tmp_path / "clip_square.mp4"
        extractor._extract_clip(
            input_path=test_video,
            output_path=output,
            start=1.0,
            end=5.0,
            format_preset="square",
        )
        assert output.exists()
        meta = extractor.ffmpeg.get_metadata(output)
        # Square: width should equal height (within 2px for rounding)
        assert abs(meta.width - meta.height) <= 2, (
            f"Expected square video, got {meta.width}x{meta.height}"
        )

    def test_landscape_no_crop_needed(self, extractor, test_video, tmp_path):
        """A 16:9 source with landscape preset should not be cropped."""
        output = tmp_path / "clip_landscape.mp4"
        extractor._extract_clip(
            input_path=test_video,
            output_path=output,
            start=1.0,
            end=5.0,
            format_preset="landscape",
        )
        assert output.exists()
        meta = extractor.ffmpeg.get_metadata(output)
        # Should preserve original 1920x1080 (or close, since stream copy)
        assert meta.width >= meta.height
