import pytest
import json
from pathlib import Path

from skill_script import ScriptGenerator, STYLE_TEMPLATES


@pytest.fixture
def generator():
    return ScriptGenerator()


# --- Prompt building ---

def test_build_prompt(generator):
    prompt = generator._build_prompt(
        brief="30-second palm oil ad for FOFAL",
        style="ad",
        language="en",
    )
    assert "palm oil" in prompt.lower()
    assert "ad" in prompt
    assert "persuasive" in prompt.lower()
    assert len(prompt) > 50


def test_build_prompt_with_transcript(generator):
    prompt = generator._build_prompt(
        brief="Improve this corporate video",
        style="corporate",
        language="en",
        transcript="Welcome to FOFAL. We produce sustainable palm oil.",
    )
    assert "sustainable palm oil" in prompt.lower()
    assert "corporate" in prompt.lower()
    assert "transcript" in prompt.lower()


def test_build_prompt_all_styles(generator):
    """Every supported style should produce a valid prompt."""
    for style in STYLE_TEMPLATES:
        prompt = generator._build_prompt(
            brief="Test brief",
            style=style,
            language="en",
        )
        assert len(prompt) > 50
        assert style in prompt


# --- Template script generation ---

def test_generate_template_script(generator):
    panels = generator._generate_template_script(
        brief="A corporate video about sustainable palm oil production at FOFAL plantation",
        style="corporate",
        target_duration=60,
        language="en",
    )
    assert len(panels) >= 3
    assert all("visual" in p and "audio" in p and "text" in p for p in panels)
    total = sum(p["duration"] for p in panels)
    assert abs(total - 60) < 1.0  # within 1 second of target


def test_generate_template_script_ad_style(generator):
    panels = generator._generate_template_script(
        brief="30-second FOFAL palm oil ad",
        style="ad",
        target_duration=30,
        language="en",
    )
    assert len(panels) >= 3
    total = sum(p["duration"] for p in panels)
    assert abs(total - 30) < 1.0


def test_generate_template_script_tutorial_style(generator):
    panels = generator._generate_template_script(
        brief="How to use the FOFAL ERP system. Login to the dashboard. Navigate modules.",
        style="tutorial",
        target_duration=120,
        language="en",
    )
    assert len(panels) >= 4
    total = sum(p["duration"] for p in panels)
    assert abs(total - 120) < 1.0


def test_template_panels_have_sequential_timing(generator):
    """Panels should have contiguous, non-overlapping time ranges."""
    panels = generator._generate_template_script(
        brief="Test video for timing",
        style="social",
        target_duration=45,
        language="en",
    )
    for i in range(len(panels) - 1):
        assert panels[i]["end"] == pytest.approx(panels[i + 1]["start"], abs=0.01)
    assert panels[0]["start"] == pytest.approx(0.0, abs=0.01)


# --- Script parsing ---

def test_parse_script_to_storyboard(generator):
    script = (
        "SCENE 1: Opening\n"
        "VISUAL: Wide shot of plantation\n"
        "AUDIO: Ambient nature sounds\n"
        "TEXT: FOFAL Plantation\n"
        "NOTES: Drone shot preferred\n"
        "\n"
        "SCENE 2: Production\n"
        "VISUAL: Workers harvesting palm fruit\n"
        "AUDIO: Narrator explains process\n"
        "TEXT: Sustainable Harvesting\n"
        "NOTES: Close-up shots\n"
    )
    panels = generator._parse_script_to_storyboard(script, target_duration=30)
    assert len(panels) == 2
    assert panels[0]["scene"] == 1
    assert panels[0]["visual"] == "Wide shot of plantation"
    assert panels[0]["audio"] == "Ambient nature sounds"
    assert panels[1]["scene"] == 2
    total = sum(p["duration"] for p in panels)
    assert abs(total - 30) < 0.1


def test_parse_empty_script(generator):
    panels = generator._parse_script_to_storyboard("", target_duration=30)
    assert panels == []


# --- Execute (full V-I-V cycle) ---

def test_execute_with_brief(generator, tmp_path):
    output = tmp_path / "storyboard.json"
    result = generator.execute(
        brief="A 30-second advertisement for organic palm oil",
        output_path=output,
        target_duration=30,
        style="ad",
        language="en",
    )
    assert output.exists()
    assert result["panels_count"] >= 3
    assert result["total_duration"] > 0

    with open(output) as f:
        storyboard = json.load(f)
    assert len(storyboard["panels"]) >= 3


def test_execute_creates_parent_dirs(generator, tmp_path):
    output = tmp_path / "subdir" / "deep" / "storyboard.json"
    result = generator.execute(
        brief="Test video brief",
        output_path=output,
        target_duration=60,
    )
    assert output.exists()
    assert result["panels_count"] >= 3


def test_execute_rejects_empty_brief(generator, tmp_path):
    with pytest.raises(ValueError, match="Brief cannot be empty"):
        generator.execute(
            brief="",
            output_path=tmp_path / "out.json",
        )


def test_execute_rejects_whitespace_brief(generator, tmp_path):
    with pytest.raises(ValueError, match="Brief cannot be empty"):
        generator.execute(
            brief="   ",
            output_path=tmp_path / "out.json",
        )


def test_execute_rejects_missing_video(generator, tmp_path):
    with pytest.raises(FileNotFoundError):
        generator.execute(
            brief="Test",
            output_path=tmp_path / "out.json",
            video_input=Path("/nonexistent/video.mp4"),
        )


def test_execute_rejects_invalid_style(generator, tmp_path):
    with pytest.raises(ValueError, match="Unknown style"):
        generator.execute(
            brief="Test",
            output_path=tmp_path / "out.json",
            style="unknown_style",
        )


def test_execute_rejects_negative_duration(generator, tmp_path):
    with pytest.raises(ValueError, match="positive"):
        generator.execute(
            brief="Test",
            output_path=tmp_path / "out.json",
            target_duration=-10,
        )


# --- Save and load storyboard ---

def test_save_and_load_storyboard(generator, tmp_path):
    panels = [
        {"scene": 1, "start": 0, "end": 10, "duration": 10,
         "visual": "Opening", "audio": "Music", "text": "Title", "notes": ""},
        {"scene": 2, "start": 10, "end": 20, "duration": 10,
         "visual": "Content", "audio": "Voice", "text": "Body", "notes": ""},
    ]
    output = tmp_path / "test_storyboard.json"
    generator._save_storyboard(panels, output)

    assert output.exists()
    with open(output) as f:
        data = json.load(f)
    assert len(data["panels"]) == 2
    assert data["metadata"]["total_duration"] == 20
    assert data["metadata"]["panels_count"] == 2
    assert "generated_at" in data["metadata"]


def test_save_storyboard_utf8(generator, tmp_path):
    """Should handle non-ASCII text correctly."""
    panels = [
        {"scene": 1, "start": 0, "end": 15, "duration": 15,
         "visual": "Vue de la plantation", "audio": "Musique africaine",
         "text": "Bienvenue a FOFAL", "notes": "Region du Centre, Cameroun"},
    ]
    output = tmp_path / "french_storyboard.json"
    generator._save_storyboard(panels, output)

    with open(output, encoding="utf-8") as f:
        data = json.load(f)
    assert "Region du Centre" in data["panels"][0]["notes"]


# --- Internal helpers ---

def test_split_brief_multiple_sentences(generator):
    brief = "FOFAL produces palm oil. The plantation spans 80 hectares. Workers harvest daily. Quality is certified."
    parts = generator._split_brief(brief, 4)
    assert len(parts) == 4
    assert all(len(p) > 0 for p in parts)


def test_split_brief_single_sentence(generator):
    brief = "A short brief"
    parts = generator._split_brief(brief, 3)
    assert len(parts) == 3


def test_extract_field(generator):
    content = "VISUAL: A wide shot\nAUDIO: Music plays\nTEXT: Title card"
    assert generator._extract_field(content, "VISUAL") == "A wide shot"
    assert generator._extract_field(content, "AUDIO") == "Music plays"
    assert generator._extract_field(content, "TEXT") == "Title card"


def test_extract_field_missing(generator):
    content = "VISUAL: Something"
    assert generator._extract_field(content, "NOTES") == ""
