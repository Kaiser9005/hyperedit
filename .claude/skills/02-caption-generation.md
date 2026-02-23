---
name: caption-generation
description: Generate captions/subtitles from video using whisper.cpp transcription
---

# Caption Generation

## When to Use
When user asks to add captions, subtitles, or generate SRT/VTT files from video.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has audio track
2. Get video duration and resolution

### IMPLEMENT
1. Extract audio from video (16kHz WAV)
2. Run whisper.cpp with word-level timestamps
3. Generate SRT and VTT caption files
4. Optionally burn captions into video with FFmpeg

### VERIFY (After)
1. All spoken words present in captions
2. Timing accuracy within ±100ms
3. SRT/VTT format valid
4. Burned-in captions readable at target resolution

## Parameters
- `language`: Transcription language (default: auto)
- `format`: Output format - srt, vtt, or both (default: both)
- `burn_in`: Whether to burn captions into video (default: false)
- `font_size`: Caption font size for burn-in (default: 24)
- `position`: Caption position - bottom, top (default: bottom)

## Example
```bash
python services/skill_captions.py --input input_videos/talk.mp4 --output output_videos/ --burn-in
```
