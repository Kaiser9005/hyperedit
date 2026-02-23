---
name: color-grading
description: Apply color grading presets, LUTs, or custom adjustments to video using FFmpeg
---

# Color Grading

## When to Use
When user asks to color grade, apply a look/mood, apply LUT, adjust colors, fix white balance, or enhance visual style.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has video stream
2. If LUT file specified, verify it exists (.cube or .3dl)

### IMPLEMENT
1. If preset specified: map to FFmpeg eq/colorbalance parameters
2. If LUT file: apply via lut3d filter
3. If manual: apply contrast/brightness/saturation/gamma adjustments

### VERIFY (After)
1. Output video exists and is playable
2. Resolution preserved
3. Duration matches input
4. QA checks pass

## Parameters
- `preset`: Named preset (warm, cool, cinematic, vintage, high_contrast, desaturated)
- `lut_path`: Path to .cube/.3dl LUT file
- `contrast`: Manual contrast (0.0-3.0, default 1.0)
- `brightness`: Manual brightness (-1.0 to 1.0, default 0.0)
- `saturation`: Manual saturation (0.0-3.0, default 1.0)
- `gamma`: Gamma correction (0.1-10.0, default 1.0)

## Example
```bash
python services/skill_color.py --input video.mp4 --output graded.mp4 --preset cinematic
```
