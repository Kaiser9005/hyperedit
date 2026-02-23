---
name: thumbnail-generation
description: Generate video thumbnails by extracting frames at key moments and scaling to target resolution
---

# Thumbnail Generation

## When to Use
When user asks to generate thumbnails, extract frames, create preview images, or pick the best frame from a video.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has a video stream
2. Validate output directory exists or can be created
3. Confirm format is supported (jpg, png)

### IMPLEMENT
1. Get video duration via FFmpeg metadata
2. Calculate extraction timestamps (evenly distributed, skipping first/last 5%)
3. Extract frames at each timestamp via FFmpeg
4. Scale each frame to target resolution (default 1280x720)
5. Identify best thumbnail by largest file size (more visual detail heuristic)

### VERIFY (After)
1. All requested thumbnails were created on disk
2. Each thumbnail file size > 1KB (not a blank/corrupt frame)
3. Return structured result with paths, timestamps, and sizes

## Parameters
- `input_path`: Source video file
- `output_dir`: Directory for extracted thumbnails
- `count`: Number of thumbnails to extract (default 3)
- `format`: Image format, jpg or png (default jpg)
- `width`: Target width in pixels (default 1280)
- `height`: Target height in pixels (default 720)
- `timestamps`: Optional list of specific timestamps (overrides count/auto-distribution)

## Example
```bash
# Auto-distributed thumbnails
python services/skill_thumbnail.py --input video.mp4 --output-dir ./thumbs --count 3

# Specific timestamps
python services/skill_thumbnail.py --input video.mp4 --output-dir ./thumbs --timestamps 1.0 5.0 8.0

# PNG format at custom resolution
python services/skill_thumbnail.py --input video.mp4 --output-dir ./thumbs --count 5 --format png --width 1920 --height 1080
```
