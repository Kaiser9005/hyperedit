import pytest
from unittest.mock import patch, MagicMock
from notification_service import NotificationService, NotificationLevel


@pytest.fixture
def notifier():
    """Notifier with Telegram disabled (no tokens)."""
    return NotificationService()


@pytest.fixture
def enabled_notifier():
    """Notifier with fake Telegram tokens."""
    return NotificationService(
        telegram_bot_token="fake-token",
        telegram_chat_id="12345",
    )


def test_disabled_notification(notifier):
    assert notifier.enabled is False
    result = notifier.notify("test message")
    assert result["sent"] is False
    assert result["level"] == "info"
    assert result["message"] == "test message"


def test_enabled_notification_flag(enabled_notifier):
    assert enabled_notifier.enabled is True


def test_skill_started(notifier):
    result = notifier.skill_started("Dead Air Removal", "video.mp4")
    assert result["level"] == "info"
    assert "Dead Air Removal" in result["message"]


def test_skill_completed(notifier):
    result = notifier.skill_completed("Captions", {"output_duration": 45.5, "time_saved": 10.2})
    assert result["level"] == "success"
    assert result["metadata"]["time_saved"] == "10.2s"


def test_skill_failed(notifier):
    result = notifier.skill_failed("Color Grading", "FFmpeg error")
    assert result["level"] == "error"
    assert "FFmpeg error" in result["message"]


def test_pipeline_started(notifier):
    result = notifier.pipeline_started("interview.mp4", ["dead_air", "captions", "audio"])
    assert result["level"] == "info"
    assert result["metadata"]["total_skills"] == 3


def test_pipeline_completed(notifier):
    result = notifier.pipeline_completed("interview.mp4", 120.5)
    assert result["level"] == "success"


def test_history_tracking(notifier):
    notifier.notify("msg1")
    notifier.notify("msg2", level=NotificationLevel.WARNING)
    history = notifier.get_history()
    assert len(history) == 2
    assert history[1]["level"] == "warning"


def test_telegram_send_mocked(enabled_notifier):
    """Test that _send_telegram is called when enabled."""
    with patch.object(enabled_notifier, "_send_telegram", return_value={"message_id": 999}) as mock_send:
        result = enabled_notifier.notify("hello")
        mock_send.assert_called_once()
        assert result["sent"] is True
        assert result["message_id"] == 999


def test_telegram_send_failure(enabled_notifier):
    """Test graceful handling when Telegram API fails."""
    with patch.object(enabled_notifier, "_send_telegram", side_effect=Exception("network error")):
        result = enabled_notifier.notify("hello")
        assert result["sent"] is False
        assert "error" in result
