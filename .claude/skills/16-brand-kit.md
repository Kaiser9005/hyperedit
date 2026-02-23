---
name: brand-kit
description: Apply brand identity (logo, colors, fonts, watermark, intro/outro) to video using FFmpeg
---

# Brand Kit Manager

## When to Use
When user asks to brand a video, add a watermark, apply company colors, add logo overlay, or create branded intro/outro.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists
2. Verify brand config exists or create default
3. If logo specified, verify image file exists

### IMPLEMENT
1. Load brand configuration (colors, fonts, logo path, watermark settings)
2. Apply watermark/logo overlay via FFmpeg overlay filter
3. Add branded text overlay (company name, tagline) via drawtext filter
4. Optionally prepend intro or append outro segments

### VERIFY (After)
1. Output video exists and plays correctly
2. Resolution preserved
3. Brand elements are applied (duration may increase if intro/outro added)

## Parameters
- `brand_config`: Path to brand JSON config file
- `add_watermark`: Add watermark overlay (default: true)
- `add_text_overlay`: Add branded text (default: false)
- `text_position`: Position for text overlay (bottom_left, bottom_right, top_left, top_right, center)
- `text_content`: Custom text to overlay

## Example
```bash
python services/skill_brand.py --input video.mp4 --output branded.mp4 --brand-config brands/fofal.json
```
