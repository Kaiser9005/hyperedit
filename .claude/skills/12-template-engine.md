---
name: template-engine
description: Apply video structure templates (intro/outro/sections) to calculate timing plans for editing workflows
---

# Template Engine

## When to Use
When user asks to apply a video template, structure a video with intro/outro, plan section timings, use a corporate/tutorial/social layout, or create a custom video structure.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has valid metadata
2. Verify requested template exists (built-in or custom JSON)
3. Confirm total duration is sufficient for fixed-duration sections

### IMPLEMENT
1. Load template definition (built-in or custom JSON file)
2. Calculate section timings: fixed-duration sections keep their values, remaining time is distributed equally among variable-duration (None) sections
3. Generate a timing plan with contiguous, non-overlapping sections that sum to input duration

### VERIFY (After)
1. All sections are contiguous (each start equals previous end)
2. Section durations sum to approximately the input video duration
3. No section has zero or negative duration

## Built-in Templates
- `corporate_ad`: Brand intro (3s) + Content + CTA (5s) + Outro (3s)
- `tutorial`: Introduction (5s) + Tutorial steps + Summary (5s) + Subscribe CTA (3s)
- `social_short`: Attention hook (3s) + Core message + Action prompt (2s)
- `product_demo`: Problem statement (3s) + Demo + Feature highlights (10s) + Where to buy (5s)

## Parameters
- `template_name`: Name of a built-in template (default: "corporate_ad")
- `custom_template`: Path to a custom template JSON file
- `input_path`: Input video file (used to determine total duration)
- `output_path`: Not written to; the engine produces a timing plan only

## Example
```bash
python services/skill_template.py --input video.mp4 --template corporate_ad
python services/skill_template.py --list
python services/skill_template.py --input video.mp4 --custom-template my_template.json
```
