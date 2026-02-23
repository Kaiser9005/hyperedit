---
name: broll-insertion
description: Insert B-roll footage at silence/transition points in video using whisper.cpp + FFmpeg
---

# B-Roll Insertion

## When to Use
When user asks to add B-roll clips, cutaway footage, or supplementary visuals at natural break points (silence gaps, pauses, transitions) in a video. Also useful for making talking-head videos more visually engaging.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has video+audio tracks
2. Check all B-roll clip paths exist and are valid video files
3. Get original metadata (duration, resolution, fps)

### IMPLEMENT
1. Analyze input for insertion opportunities:
   - **silence mode**: detect silence gaps via FFmpeg silencedetect
   - **manual mode**: use user-provided timestamps
2. Filter insertion points by minimum gap duration (default: 2.0s)
3. Prepare each B-roll clip: trim/loop to target duration, scale to match main video resolution
4. Build ordered edit list alternating main footage and B-roll segments
5. Cut main video around insertion points
6. Interleave B-roll clips at insertion points
7. Concatenate all segments into final output

### VERIFY (After)
1. Output file exists and is playable
2. Output duration is reasonable (>= input duration since we replace silence, not add)
3. QA checks pass (resolution, audio present, no black frames)

## Parameters
- `mode`: Detection mode - "silence" (auto-detect) or "manual" (user timestamps) (default: silence)
- `max_insertions`: Maximum number of B-roll insertions (default: 5)
- `min_gap`: Minimum silence gap duration to consider for insertion (default: 2.0s)
- `broll_clips`: List of B-roll video file paths to insert

## Example
```bash
python services/skill_broll.py --input input_videos/interview.mp4 --output output_videos/interview_broll.mp4 --broll clips/office.mp4 clips/product.mp4 --mode silence --max-insertions 3
```
