---
name: style-transfer
description: Clone the visual style of a reference video onto a target video, or apply curated style presets using FFmpeg
---

# Style Transfer

## When to Use
When user asks to clone a video's look, match the style of another video, apply a film look (noir, VHS, dreamy, cinematic), transfer color grading between videos, or emulate a popular visual aesthetic.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has a video stream
2. If reference video specified, verify it exists and has a video stream
3. Ensure at least one of `style` or `reference_path` is provided

### IMPLEMENT
1. If style preset: apply the preset's FFmpeg filter chain (eq, colorbalance, noise, gblur, unsharp)
2. If reference video: analyze reference color characteristics via FFmpeg signalstats (YAVG, UAVG, VAVG), then approximate by adjusting contrast/brightness/saturation on the input

### VERIFY (After)
1. Output video exists and is playable
2. Resolution preserved (matches input)
3. Duration preserved (within 0.5s tolerance)
4. QA checks pass

## Style Presets
- `film_noir`: Desaturated, high contrast, slightly dark with lifted gamma
- `vhs_retro`: Reduced saturation, low contrast, slight brightness boost, noise, soft unsharp
- `instagram_warm`: Boosted saturation and contrast, warm color balance shift
- `cool_blue`: Slight desaturation with blue-shifted color balance
- `high_contrast_bw`: Full desaturation with very high contrast and lifted gamma
- `dreamy`: Slight saturation boost, brightness lift, gaussian blur for soft glow
- `cinematic_teal_orange`: Contrast and saturation boost with teal shadows and orange highlights

## Parameters
- `style`: Named style preset (film_noir, vhs_retro, instagram_warm, cool_blue, high_contrast_bw, dreamy, cinematic_teal_orange)
- `reference_path`: Path to a reference video whose visual style should be matched

## Example
```bash
# Apply a preset
python services/skill_style.py --input video.mp4 --output styled.mp4 --style film_noir

# Match a reference video's look
python services/skill_style.py --input video.mp4 --output styled.mp4 --reference ref.mp4
```
