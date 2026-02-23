---
name: multi-format-export
description: Export video to multiple formats and resolutions for different platforms
---

# Multi-Format Export

## When to Use
When user asks to export video for YouTube, Instagram, TikTok, Twitter, or web. When user needs multiple resolution/format outputs from a single source video, or wants a GIF preview.

## Process (V-I-V)
### VERIFY: Check input exists, get metadata (resolution, duration, codec)
### IMPLEMENT: Transcode to each requested profile with correct resolution, bitrate, codec. GIF uses palette generation for quality.
### VERIFY: Each output has correct resolution, codec, file size > 0, duration matches source

## Profiles
- `youtube_4k`: 3840x2160, 20Mbps, H.264, 320k audio
- `youtube_1080p`: 1920x1080, 8Mbps, H.264, 192k audio
- `youtube_720p`: 1280x720, 5Mbps, H.264, 128k audio
- `instagram_reels`: 1080x1920 (vertical), 6Mbps, H.264, 192k audio
- `tiktok`: 1080x1920 (vertical), 6Mbps, H.264, 192k audio
- `twitter`: 1280x720, 5Mbps, H.264, 128k audio
- `web_optimized`: 1920x1080, 4Mbps, H.264, 128k audio
- `gif_preview`: 480x270, 10fps, no audio

## Parameters
- `input_path`: Source video file
- `output_dir`: Directory for exported files
- `profiles`: List of profile names (default: youtube_1080p + web_optimized)

## CLI Usage
```bash
python services/skill_export.py --input video.mp4 --output-dir ./exports
python services/skill_export.py --input video.mp4 --output-dir ./exports --profiles youtube_4k instagram_reels gif_preview
```
