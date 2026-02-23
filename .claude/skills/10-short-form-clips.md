---
name: short-form-clip-extraction
description: Extract short-form clips (TikTok, Reels, Shorts) from longer videos using whisper.cpp + FFmpeg
---

# Short-Form Clip Extraction

## When to Use
When user asks to create TikTok clips, Instagram Reels, YouTube Shorts, or any short-form vertical content from a longer video. Also when repurposing long-form content (interviews, podcasts, tutorials) into bite-sized clips.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has both audio and video tracks
2. Get original metadata (duration, resolution, aspect ratio)

### IMPLEMENT
1. Transcribe audio with word-level timestamps via whisper.cpp
2. Detect silence gaps as natural segment break points
3. Score transcript segments by speech density (words per second)
4. Group segments into candidate clips within duration limits
5. Select top N highest-scored candidates
6. Extract each clip via FFmpeg cut
7. Crop to target aspect ratio (9:16 for vertical, 1:1 for square)

### VERIFY (After)
1. All clips created and exist on disk
2. Each clip duration within min/max limits
3. QA checks pass (resolution, audio present, no black frames)

## Format Presets
- `tiktok`: max 60s, 9:16, 1080x1920
- `reels`: max 90s, 9:16, 1080x1920
- `shorts`: max 60s, 9:16, 1080x1920
- `square`: max 60s, 1:1, 1080x1080
- `landscape`: max 120s, 16:9, 1920x1080

## Parameters
- `format_preset`: Target platform preset (default: shorts)
- `max_clips`: Maximum number of clips to extract (default: 5)
- `min_clip_duration`: Minimum clip length in seconds (default: 10)
- `max_clip_duration`: Maximum clip length in seconds (default: 60)
- `language`: Transcription language (default: auto)

## Example
```bash
python services/skill_shortform.py --input input_videos/interview.mp4 --output-dir output_videos/clips/ --format shorts --max-clips 3
```
