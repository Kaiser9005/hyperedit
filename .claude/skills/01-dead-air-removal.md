---
name: dead-air-removal
description: Remove dead air, silence, and filler words from video using whisper.cpp + FFmpeg
---

# Dead Air & Silence Removal

## When to Use
When user asks to clean up a video, remove silences, remove "ums" and "uhs", or tighten pacing.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has audio track
2. Get original duration for comparison

### IMPLEMENT
1. Extract audio from video (16kHz WAV)
2. Run whisper.cpp transcription with word-level timestamps
3. Detect silence segments (>1.5s below -40dB)
4. Detect filler words (um, uh, euh, alors, etc.)
5. Build cut list (segments to KEEP)
6. FFmpeg: extract kept segments and concatenate

### VERIFY (After)
1. Output duration < input duration
2. Re-transcribe output: 0 filler words detected
3. No audio sync issues
4. QA checks pass (resolution, audio, no black frames)

## Parameters
- `silence_threshold_db`: Noise floor for silence detection (default: -40)
- `min_silence_duration`: Minimum silence to remove (default: 1.5s)
- `remove_fillers`: Whether to remove filler words (default: true)
- `language`: Transcription language (default: auto)

## Example
```bash
python services/skill_dead_air.py --input input_videos/interview.mp4 --output output_videos/interview_clean.mp4
```
