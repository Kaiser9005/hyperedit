---
name: youtube-publishing
description: Publish videos to YouTube with metadata, descriptions, chapters, and thumbnails
---

# YouTube Publishing

## When to Use
When user asks to publish a video to YouTube, upload to YouTube, set video metadata (title, description, tags, category, privacy), format a YouTube description with chapters, or manage thumbnails for YouTube uploads.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video file exists and is a valid format
2. Verify YouTube API credentials are available (YOUTUBE_API_KEY, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
3. Validate title is not empty
4. Validate video duration < 12 hours and file size < 256 GB

### IMPLEMENT
1. Build YouTube metadata dict (title, description, tags, category, privacy)
2. Format rich description with chapters, hashtags, and links if provided
3. Upload video via YouTube Data API v3 (resumable upload)
4. Optionally set custom thumbnail

### VERIFY (After)
1. Upload result contains a valid video ID
2. Video URL is well-formed (https://youtu.be/{video_id})
3. Upload status is reported correctly

## Parameters
- `video_path`: Path to the video file to upload
- `title`: Video title (required, max 100 characters)
- `description`: Video description text
- `tags`: List of tags for discoverability
- `category`: YouTube category ID (default: "22" for People & Blogs)
- `privacy`: Privacy status — private, unlisted, or public (default: private)
- `thumbnail_path`: Optional custom thumbnail image path

## Example
```bash
python services/skill_youtube.py --input video.mp4 --title "My Video" --description "A great video" --tags "tutorial,python" --privacy unlisted
```
