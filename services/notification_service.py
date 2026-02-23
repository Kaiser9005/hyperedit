"""Notification service for video editing pipeline status updates."""

import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationService:
    """Send pipeline status updates via Telegram or log fallback."""

    EMOJI_MAP = {
        NotificationLevel.INFO: "ℹ️",
        NotificationLevel.SUCCESS: "✅",
        NotificationLevel.WARNING: "⚠️",
        NotificationLevel.ERROR: "❌",
    }

    def __init__(
        self,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        self.bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        self._history: list[dict] = []

        if not self.enabled:
            logger.info("Telegram not configured — notifications will be logged only")

    def notify(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Send a notification. Returns dict with status and message_id."""
        emoji = self.EMOJI_MAP.get(level, "")
        timestamp = datetime.now().isoformat()
        full_message = f"{emoji} *HyperEdit AI* [{level.value.upper()}]\n\n{message}"

        if metadata:
            details = "\n".join(f"• {k}: {v}" for k, v in metadata.items())
            full_message += f"\n\n📊 Details:\n{details}"

        full_message += f"\n\n🕐 {timestamp}"

        record = {
            "timestamp": timestamp,
            "level": level.value,
            "message": message,
            "metadata": metadata,
            "sent": False,
            "message_id": None,
        }

        if self.enabled:
            try:
                result = self._send_telegram(full_message)
                record["sent"] = True
                record["message_id"] = result.get("message_id")
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
                record["error"] = str(e)
        else:
            logger.info(f"[NOTIFICATION] {level.value}: {message}")

        self._history.append(record)
        return record

    def _send_telegram(self, text: str) -> dict:
        """Send message via Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        response = httpx.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return {"message_id": data["result"]["message_id"]}

    def skill_started(self, skill_name: str, input_file: str) -> dict:
        """Notify that a skill execution has started."""
        return self.notify(
            f"Starting *{skill_name}*",
            level=NotificationLevel.INFO,
            metadata={"input": input_file},
        )

    def skill_completed(self, skill_name: str, result: dict) -> dict:
        """Notify that a skill execution completed successfully."""
        meta = {}
        if "time_saved" in result:
            meta["time_saved"] = f"{result['time_saved']:.1f}s"
        if "output_duration" in result:
            meta["output_duration"] = f"{result['output_duration']:.1f}s"
        if "panels_count" in result:
            meta["panels"] = result["panels_count"]
        return self.notify(
            f"Completed *{skill_name}*",
            level=NotificationLevel.SUCCESS,
            metadata=meta or None,
        )

    def skill_failed(self, skill_name: str, error: str) -> dict:
        """Notify that a skill execution failed."""
        return self.notify(
            f"Failed *{skill_name}*: {error}",
            level=NotificationLevel.ERROR,
        )

    def pipeline_started(self, video_name: str, skills: list[str]) -> dict:
        """Notify full pipeline start."""
        return self.notify(
            f"Pipeline started for *{video_name}*\nSkills: {', '.join(skills)}",
            level=NotificationLevel.INFO,
            metadata={"total_skills": len(skills)},
        )

    def pipeline_completed(self, video_name: str, total_time: float) -> dict:
        """Notify full pipeline completion."""
        return self.notify(
            f"Pipeline complete for *{video_name}*",
            level=NotificationLevel.SUCCESS,
            metadata={"total_time": f"{total_time:.1f}s"},
        )

    def get_history(self) -> list[dict]:
        """Return notification history."""
        return self._history.copy()
