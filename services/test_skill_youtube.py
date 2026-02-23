"""Tests for Skill 17: YouTube Publishing."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from skill_youtube import YouTubePublisher


@pytest.fixture
def publisher():
    return YouTubePublisher()


@pytest.fixture
def test_video(tmp_path):
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_build_metadata(publisher):
    """Verify metadata structure with title, description, tags, category, privacy."""
    meta = publisher._build_metadata(
        title="Test Video",
        description="A test description",
        tags=["python", "tutorial"],
        category="27",
        privacy="unlisted",
    )
    assert meta["snippet"]["title"] == "Test Video"
    assert meta["snippet"]["description"] == "A test description"
    assert meta["snippet"]["tags"] == ["python", "tutorial"]
    assert meta["snippet"]["categoryId"] == "27"
    assert meta["status"]["privacyStatus"] == "unlisted"
    assert meta["status"]["selfDeclaredMadeForKids"] is False


def test_validate_video_ok(publisher, test_video):
    """Valid test video passes validation."""
    result = publisher._validate_video(test_video)
    assert result["valid"] is True
    assert result["duration"] > 0
    assert result["file_size"] > 0


def test_validate_video_missing(publisher, tmp_path):
    """Missing file raises FileNotFoundError."""
    missing = tmp_path / "nonexistent.mp4"
    with pytest.raises(FileNotFoundError):
        publisher._validate_video(missing)


def test_format_description(publisher):
    """Test basic description with links."""
    result = publisher.format_description(
        description="Check out this video",
        links={"Website": "https://example.com", "GitHub": "https://github.com/test"},
    )
    assert "Check out this video" in result
    assert "Website: https://example.com" in result
    assert "GitHub: https://github.com/test" in result


def test_format_description_with_chapters(publisher):
    """Chapters formatted as YouTube timestamps."""
    result = publisher.format_description(
        description="Tutorial video",
        chapters=[
            {"time": 0, "title": "Intro"},
            {"time": 120, "title": "Setup"},
            {"time": 3661, "title": "Advanced Topic"},
        ],
        tags=["python", "tutorial"],
    )
    assert "Chapters:" in result
    assert "0:00 Intro" in result
    assert "2:00 Setup" in result
    assert "1:01:01 Advanced Topic" in result
    assert "#python #tutorial" in result


def test_list_categories(publisher):
    """Verify common categories present."""
    cats = publisher.list_categories()
    assert "22" in cats
    assert cats["22"] == "People & Blogs"
    assert "27" in cats
    assert cats["27"] == "Education"
    assert "28" in cats
    assert cats["28"] == "Science & Technology"
    assert "10" in cats
    assert cats["10"] == "Music"


def test_execute_no_credentials(publisher, test_video):
    """Raises ValueError when no API credentials."""
    # publisher.enabled is False by default (no env vars set)
    assert publisher.enabled is False
    with pytest.raises(ValueError, match="YouTube API credentials not configured"):
        publisher.execute(
            video_path=test_video,
            title="Test",
        )


def test_execute_empty_title(test_video):
    """Raises ValueError for empty title."""
    pub = YouTubePublisher()
    # Force enabled to bypass credential check
    pub.enabled = True
    with pytest.raises(ValueError, match="title must not be empty"):
        pub.execute(video_path=test_video, title="")

    with pytest.raises(ValueError, match="title must not be empty"):
        pub.execute(video_path=test_video, title="   ")


def test_execute_with_mock_upload(test_video):
    """Mock _upload_video, verify full execute cycle."""
    pub = YouTubePublisher()
    pub.enabled = True

    mock_response = {"video_id": "abc123XYZ", "status": "uploaded"}

    with patch.object(pub, "_upload_video", return_value=mock_response):
        result = pub.execute(
            video_path=test_video,
            title="My Test Upload",
            description="Testing the upload flow",
            tags=["test", "automation"],
            category="28",
            privacy="unlisted",
        )

    assert result["video_id"] == "abc123XYZ"
    assert result["url"] == "https://youtu.be/abc123XYZ"
    assert result["title"] == "My Test Upload"
    assert result["privacy"] == "unlisted"
    assert result["upload_status"] == "uploaded"
