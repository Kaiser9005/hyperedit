---
name: chapter-generation
description: Generate video chapters from transcription using silence detection + topic signal analysis
---

# Chapter Generation

## When to Use
When user asks to generate chapters, timestamps, or a table of contents for a video. Also when preparing YouTube descriptions with chapter markers or creating navigation points for long-form content.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has audio track
2. Get video duration (must be >60s for meaningful chapters)

### IMPLEMENT
1. Extract audio from video (16kHz WAV)
2. Run whisper.cpp transcription with word-level timestamps
3. Detect silence segments as potential chapter break points
4. Score silences using topic signal words (en/fr) and position
5. Select best chapter boundaries respecting min_chapter_duration
6. Generate chapter titles from transcript text at each boundary
7. Save output as JSON and/or YouTube timestamp format

### VERIFY (After)
1. First chapter starts at 0:00 (YouTube requirement)
2. All chapters have non-empty titles
3. No chapter shorter than min_chapter_duration
4. Chapter count within max_chapters limit
5. Chapters cover the full video duration

## Parameters
- `min_chapter_duration`: Minimum seconds per chapter (default: 30)
- `max_chapters`: Maximum number of chapters (default: 20)
- `output_format`: Output format - json, youtube, or both (default: both)
- `language`: Transcription language for topic signals (default: auto)

## Example
```bash
python services/skill_chapters.py --input input_videos/lecture.mp4 --output output_videos/lecture_chapters
```

Output files:
- `lecture_chapters.json` — structured chapter data
- `lecture_chapters_youtube.txt` — copy-paste YouTube description timestamps
