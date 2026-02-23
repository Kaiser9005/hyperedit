---
name: script-storyboard
description: Generate video scripts and storyboards from a brief or existing video using Claude API
---

# Script & Storyboard Generation

## When to Use
When user asks to generate a script for a video, create a storyboard, plan video content, or break down a video into scenes.

## Process (V-I-V)

### VERIFY (Before)
1. Check brief/input exists (text brief or video file)
2. Validate target duration and format constraints

### IMPLEMENT
1. If video input: transcribe with whisper.cpp to extract content
2. Generate script using Claude API (scene descriptions, dialogue, timing)
3. Break script into storyboard panels (scene, duration, visual, audio, text)
4. Export storyboard as JSON

### VERIFY (After)
1. Script covers all brief requirements
2. Total storyboard duration matches target
3. Each panel has complete metadata

## Parameters
- `brief`: Text description of desired video content
- `video_input`: Optional existing video to analyze
- `target_duration`: Target video length in seconds (default: 60)
- `style`: Video style (corporate, social, tutorial, ad)
- `language`: Script language (default: en)

## Example
```bash
python services/skill_script.py --brief "30-second FOFAL palm oil ad" --style ad --duration 30
```
