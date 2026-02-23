"""Integration tests — verify skills chain correctly."""

import pytest
import os
import json
from pathlib import Path


@pytest.fixture
def test_video(tmp_path):
    """Create a 10s test video with audio."""
    path = tmp_path / "integration_test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=10" '
        f'-f lavfi -i "sine=frequency=440:duration=10" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


class TestServiceImports:
    """Verify all services can be imported."""

    def test_import_ffmpeg_service(self):
        from ffmpeg_service import FFmpegService
        svc = FFmpegService()
        assert svc is not None

    def test_import_whisper_service(self):
        from whisper_service import WhisperService
        svc = WhisperService()
        assert svc is not None

    def test_import_quality_assurance(self):
        from quality_assurance import QualityAssurance
        svc = QualityAssurance()
        assert svc is not None

    def test_import_notification_service(self):
        from notification_service import NotificationService
        svc = NotificationService()
        assert svc is not None

    def test_import_scheduler_service(self):
        from scheduler_service import SchedulerService
        # Don't create real dirs
        assert SchedulerService is not None

    def test_import_all_skills(self):
        from skill_dead_air import DeadAirRemoval
        from skill_captions import CaptionGeneration
        from skill_audio import AudioEnhancement
        from skill_color import ColorGrading
        from skill_brand import BrandKitManager
        from skill_transitions import TransitionManager
        from skill_chapters import ChapterGenerator
        from skill_animation import AnimationOverlay
        from skill_style import StyleTransfer
        from skill_broll import BRollInserter
        from skill_shortform import ShortFormExtractor
        from skill_export import MultiFormatExporter
        from skill_script import ScriptGenerator
        from skill_thumbnail import ThumbnailGenerator
        from skill_gif import GifManager
        from skill_youtube import YouTubePublisher
        from skill_voiceover import VoiceoverGenerator
        from skill_template import TemplateEngine
        # All 18 skills imported
        assert True

    def test_import_batch_processor(self):
        from batch_processor import BatchProcessor
        assert BatchProcessor is not None


class TestSkillChaining:
    """Test that skills chain — output of one feeds into next."""

    def test_color_then_audio(self, test_video, tmp_path):
        from skill_color import ColorGrading
        from skill_audio import AudioEnhancement

        # Step 1: Color grade
        color_out = tmp_path / "color.mp4"
        cg = ColorGrading()
        r1 = cg.execute(test_video, color_out, preset="warm")
        assert color_out.exists()

        # Step 2: Audio enhance (from color output)
        audio_out = tmp_path / "audio.mp4"
        ae = AudioEnhancement()
        r2 = ae.execute(color_out, audio_out)
        assert audio_out.exists()
        # Color output duration should roughly match audio input
        assert r1["output_duration"] > 0

    def test_color_then_transition(self, test_video, tmp_path):
        from skill_color import ColorGrading
        from skill_transitions import TransitionManager

        color_out = tmp_path / "graded.mp4"
        cg = ColorGrading()
        cg.execute(test_video, color_out, preset="cinematic")

        fade_out = tmp_path / "faded.mp4"
        tm = TransitionManager()
        result = tm.execute(color_out, fade_out, transition_type="fade", position="both")
        assert fade_out.exists()


class TestQualityAssurance:
    """Test QA works on all outputs."""

    def test_qa_on_color_output(self, test_video, tmp_path):
        from skill_color import ColorGrading
        from quality_assurance import QualityAssurance

        output = tmp_path / "qa_test.mp4"
        cg = ColorGrading()
        cg.execute(test_video, output, preset="cinematic")

        qa = QualityAssurance()
        results = qa.full_check(output, min_width=1920, min_height=1080)
        assert all(r.passed for r in results)


class TestMetadataConsistency:
    """Verify metadata is preserved across skill chain."""

    def test_resolution_preserved(self, test_video, tmp_path):
        from ffmpeg_service import FFmpegService
        from skill_color import ColorGrading

        ff = FFmpegService()
        original = ff.get_metadata(test_video)

        output = tmp_path / "res_check.mp4"
        cg = ColorGrading()
        cg.execute(test_video, output, preset="warm")

        processed = ff.get_metadata(output)
        assert processed.width == original.width
        assert processed.height == original.height

    def test_audio_preserved(self, test_video, tmp_path):
        from ffmpeg_service import FFmpegService
        from skill_color import ColorGrading

        output = tmp_path / "audio_check.mp4"
        cg = ColorGrading()
        cg.execute(test_video, output, preset="cool")

        ff = FFmpegService()
        meta = ff.get_metadata(output)
        assert meta.has_audio is True
