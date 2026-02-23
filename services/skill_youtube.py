"""Skill 17: YouTube Publishing.

Publish videos to YouTube with metadata, descriptions, chapters, and thumbnails.
Uses the YouTube Data API v3 for uploads. The actual upload method (_upload_video)
is a placeholder that raises NotImplementedError — install google-api-python-client
to implement the real upload flow.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from ffmpeg_service import FFmpegService

# Maximum limits enforced by YouTube
MAX_DURATION_HOURS = 12
MAX_DURATION_SECONDS = MAX_DURATION_HOURS * 3600  # 43200
MAX_FILE_SIZE_GB = 256
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_GB * 1024 * 1024 * 1024

# Common video file extensions accepted by YouTube
VALID_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm",
    ".mpg", ".mpeg", ".m4v", ".3gp", ".3g2",
}

# YouTube video category IDs (common subset)
YOUTUBE_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}


class YouTubePublisher:
    """Publish videos to YouTube with metadata and description formatting."""

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.enabled = bool(self.api_key and self.client_id and self.client_secret)
        self.ffmpeg = FFmpegService()

    def execute(
        self,
        video_path: str | Path,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        category: str = "22",
        privacy: str = "private",
        thumbnail_path: Optional[str | Path] = None,
    ) -> dict:
        """Full V-I-V cycle for YouTube video publishing.

        Args:
            video_path: Path to the video file to upload.
            title: Video title (required).
            description: Video description text.
            tags: List of tags for discoverability.
            category: YouTube category ID (default "22" = People & Blogs).
            privacy: Privacy status — private, unlisted, or public.
            thumbnail_path: Optional path to a custom thumbnail image.

        Returns:
            Dict with video_id, url, title, privacy, and upload_status.

        Raises:
            FileNotFoundError: If video file does not exist.
            ValueError: If credentials are missing, title is empty,
                        or video fails validation.
        """
        video_path = Path(video_path)

        # === VERIFY (Before) ===
        if not self.enabled:
            raise ValueError(
                "YouTube API credentials not configured. "
                "Set YOUTUBE_API_KEY, YOUTUBE_CLIENT_ID, and "
                "YOUTUBE_CLIENT_SECRET environment variables."
            )

        if not title or not title.strip():
            raise ValueError("Video title must not be empty.")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        validation = self._validate_video(video_path)
        if not validation["valid"]:
            raise ValueError(
                f"Video validation failed: {validation.get('error', 'unknown')}"
            )

        # === IMPLEMENT ===
        metadata = self._build_metadata(title, description, tags, category, privacy)
        upload_result = self._upload_video(video_path, metadata)

        # Set thumbnail if provided
        if thumbnail_path:
            thumbnail_path = Path(thumbnail_path)
            if thumbnail_path.exists():
                self._set_thumbnail(upload_result["video_id"], thumbnail_path)

        # === VERIFY (After) ===
        video_id = upload_result.get("video_id")
        if not video_id:
            raise RuntimeError("Upload did not return a video ID.")

        return {
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "title": title,
            "privacy": privacy,
            "upload_status": upload_result.get("status", "uploaded"),
        }

    def _build_metadata(
        self,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        category: str = "22",
        privacy: str = "private",
    ) -> dict:
        """Build YouTube Data API v3 metadata dict.

        Args:
            title: Video title.
            description: Video description.
            tags: List of keyword tags.
            category: YouTube category ID.
            privacy: Privacy status (private, unlisted, public).

        Returns:
            Dict structured for the YouTube API videos.insert endpoint.
        """
        body = {
            "snippet": {
                "title": title.strip(),
                "description": description,
                "tags": tags or [],
                "categoryId": category,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        return body

    def _validate_video(self, video_path: Path) -> dict:
        """Validate video file for YouTube upload constraints.

        Checks:
            - File exists
            - File extension is a known video format
            - File size <= 256 GB
            - Duration <= 12 hours

        Args:
            video_path: Path to the video file.

        Returns:
            Dict with 'valid' bool and optional 'error', 'duration', 'file_size' keys.

        Raises:
            FileNotFoundError: If the video file does not exist.
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Check extension
        ext = video_path.suffix.lower()
        if ext not in VALID_EXTENSIONS:
            return {
                "valid": False,
                "error": f"Unsupported format '{ext}'. Accepted: {', '.join(sorted(VALID_EXTENSIONS))}",
            }

        # Check file size
        file_size = video_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            size_gb = file_size / (1024 ** 3)
            return {
                "valid": False,
                "error": f"File size {size_gb:.1f} GB exceeds {MAX_FILE_SIZE_GB} GB limit.",
                "file_size": file_size,
            }

        # Check duration via FFmpeg
        try:
            meta = self.ffmpeg.get_metadata(video_path)
            duration = meta.duration
        except Exception as e:
            return {
                "valid": False,
                "error": f"Could not read video metadata: {e}",
            }

        if duration > MAX_DURATION_SECONDS:
            hours = duration / 3600
            return {
                "valid": False,
                "error": f"Duration {hours:.1f}h exceeds {MAX_DURATION_HOURS}h limit.",
                "duration": duration,
                "file_size": file_size,
            }

        return {
            "valid": True,
            "duration": duration,
            "file_size": file_size,
        }

    def _upload_video(self, video_path: Path, metadata: dict) -> dict:
        """Upload video to YouTube via Data API v3.

        This is a placeholder that raises NotImplementedError.
        To implement the real upload, install the Google SDK:

            pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

        Then implement OAuth2 flow and resumable upload using
        googleapiclient.discovery.build("youtube", "v3") and
        MediaFileUpload with resumable=True.

        Args:
            video_path: Path to the video file.
            metadata: YouTube API metadata dict from _build_metadata().

        Returns:
            Dict with 'video_id' and 'status'.

        Raises:
            NotImplementedError: Always, until real SDK is wired in.
        """
        raise NotImplementedError(
            "YouTube API upload requires google-api-python-client. "
            "Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    def _set_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        """Set a custom thumbnail for an uploaded video.

        Placeholder — requires the same Google SDK as _upload_video.

        Args:
            video_id: YouTube video ID.
            thumbnail_path: Path to the thumbnail image.

        Returns:
            True on success.

        Raises:
            NotImplementedError: Always, until real SDK is wired in.
        """
        raise NotImplementedError(
            "Thumbnail upload requires google-api-python-client. "
            "Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    def format_description(
        self,
        description: str,
        chapters: Optional[list[dict]] = None,
        tags: Optional[list[str]] = None,
        links: Optional[dict[str, str]] = None,
    ) -> str:
        """Format a rich YouTube description with chapters, hashtags, and links.

        Args:
            description: Main description text.
            chapters: List of dicts with 'time' (seconds) and 'title' keys.
                      Example: [{"time": 0, "title": "Intro"}, {"time": 120, "title": "Main"}]
            tags: List of hashtag strings (without '#' prefix).
            links: Dict mapping label to URL for a links section.

        Returns:
            Formatted description string ready for YouTube.
        """
        parts = [description.strip()]

        # Chapters (YouTube timestamps)
        if chapters:
            parts.append("")
            parts.append("Chapters:")
            for ch in chapters:
                ts = self._seconds_to_timestamp(ch["time"])
                parts.append(f"{ts} {ch['title']}")

        # Links section
        if links:
            parts.append("")
            for label, url in links.items():
                parts.append(f"{label}: {url}")

        # Hashtags
        if tags:
            parts.append("")
            hashtags = " ".join(f"#{t}" for t in tags)
            parts.append(hashtags)

        return "\n".join(parts)

    def list_categories(self) -> dict:
        """Return mapping of YouTube video category IDs to names.

        Returns:
            Dict mapping category ID strings to human-readable names.
        """
        return YOUTUBE_CATEGORIES.copy()

    @staticmethod
    def _seconds_to_timestamp(seconds: float) -> str:
        """Convert seconds to YouTube timestamp format (H:MM:SS or MM:SS).

        Args:
            seconds: Time in seconds.

        Returns:
            Formatted timestamp string.
        """
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish video to YouTube")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument(
        "--category",
        default="22",
        choices=list(YOUTUBE_CATEGORIES.keys()),
        help="YouTube category ID (default: 22 = People & Blogs)",
    )
    parser.add_argument(
        "--privacy",
        default="private",
        choices=["private", "unlisted", "public"],
        help="Privacy status",
    )
    parser.add_argument("--thumbnail", default=None, help="Custom thumbnail image path")

    args = parser.parse_args()

    publisher = YouTubePublisher()

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    try:
        result = publisher.execute(
            video_path=args.input,
            title=args.title,
            description=args.description,
            tags=tag_list,
            category=args.category,
            privacy=args.privacy,
            thumbnail_path=args.thumbnail,
        )
        print("\n=== YouTube Upload ===")
        print(f"Video ID: {result['video_id']}")
        print(f"URL: {result['url']}")
        print(f"Title: {result['title']}")
        print(f"Privacy: {result['privacy']}")
        print(f"Status: {result['upload_status']}")
    except NotImplementedError as e:
        print(f"\n[Placeholder] {e}")
    except (ValueError, FileNotFoundError) as e:
        print(f"\nError: {e}")
