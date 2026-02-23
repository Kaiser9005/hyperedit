---
name: gif-integration
description: Extract GIFs from video segments or convert videos to GIF with palette-based quality optimization
---

# GIF Integration

## When to Use
When user asks to create a GIF from a video, extract a GIF segment, convert video to GIF, optimize GIF file size, or generate animated thumbnails/previews.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has video stream
2. Validate time range: start < end and within video duration
3. Validate parameters (width > 0, fps > 0, max_colors 2-256)

### IMPLEMENT
1. Two-pass palette-based GIF generation for maximum quality:
   - Pass 1: Generate optimal color palette with `palettegen` filter
   - Pass 2: Apply palette with `paletteuse` filter for dithered output
2. For optimization: iteratively reduce fps/width/colors until under target size

### VERIFY (After)
1. Output GIF file exists
2. File is a valid GIF (starts with GIF87a or GIF89a magic bytes)
3. File size is within acceptable bounds

## Parameters
- `start`: Start time in seconds for segment extraction
- `end`: End time in seconds for segment extraction
- `width`: Output width in pixels (default 480, height auto-scaled)
- `fps`: Frames per second (default 15)
- `max_colors`: Maximum palette colors 2-256 (default 256)
- `max_duration`: Maximum duration for full video conversion (default 10s)
- `max_size_kb`: Target maximum file size for optimization (default 5000KB)

## Presets
- `high`: 640px, 24fps, 256 colors
- `medium`: 480px, 15fps, 128 colors
- `low`: 320px, 10fps, 64 colors
- `thumbnail`: 200px, 8fps, 32 colors

## Example
```bash
# Extract 2-second GIF segment
python services/skill_gif.py --input video.mp4 --output clip.gif --start 5.0 --end 7.0

# Convert full video to GIF (first 10 seconds)
python services/skill_gif.py --input video.mp4 --output full.gif --mode video-to-gif

# Optimize existing GIF to under 2MB
python services/skill_gif.py --input large.gif --output small.gif --mode optimize --max-size 2000
```
