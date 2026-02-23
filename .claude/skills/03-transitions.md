---
name: transitions
description: Add transitions between video segments using FFmpeg xfade and fade filters
---

# Transitions

## When to Use
When user asks to add transitions between clips, fade in/out, crossfade, dissolve, wipe, or slide between video segments.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has video stream
2. For multi-clip transitions, verify all clip paths exist

### IMPLEMENT
1. For single video fade: apply fade=t=in and/or fade=t=out filters
2. For multi-clip transitions: apply xfade filter between consecutive clips
3. Available transition types: fade, crossfade, dissolve, wipeleft, wiperight, slideup, slidedown, circleopen

### VERIFY (After)
1. Output video exists and is playable
2. Duration preserved (single fade) or expected combined duration (multi-clip minus overlap)
3. Resolution preserved
4. QA checks pass

## Parameters
- `transition_type`: Type of transition (default: fade). One of: fade, crossfade, dissolve, wipeleft, wiperight, slideup, slidedown, circleopen
- `duration`: Transition duration in seconds (default: 1.0)
- `position`: Where to apply fade on single video: start, end, or both (default: end)

## Example
```bash
# Fade in/out on a single video
python services/skill_transitions.py --input video.mp4 --output faded.mp4 --type fade --position both --duration 1.0

# Crossfade between multiple clips
python services/skill_transitions.py --clips clip1.mp4 clip2.mp4 clip3.mp4 --output merged.mp4 --type crossfade --duration 0.5
```
