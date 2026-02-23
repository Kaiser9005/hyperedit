---
name: audio-enhancement
description: Enhance audio quality with noise reduction, normalization, and background music
---

# Audio Enhancement

## When to Use
When user asks to improve audio quality, normalize volume, reduce noise, or add background music.

## Process (V-I-V)
### VERIFY: Check input has audio, measure current LUFS
### IMPLEMENT: Noise reduce → normalize to -14 LUFS → optionally merge background music
### VERIFY: LUFS within ±1 of target, no clipping, music ducking correct

## Parameters
- `target_lufs`: Target loudness (default: -14)
- `noise_reduce`: Apply noise reduction (default: true)
- `music_path`: Optional background music file
- `music_volume`: Background music volume (default: 0.15)
