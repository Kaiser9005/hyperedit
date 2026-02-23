---
name: animation-overlays
description: Add animated text overlays, lower thirds, and motion graphics to video using FFmpeg drawtext filters
---

# Animation Overlays

## When to Use
When user asks to add text overlays, lower thirds, title cards, scrolling credits, corner badges, countdown timers, or any animated text on video.

## Process (V-I-V)

### VERIFY (Before)
1. Check input video exists and has video stream
2. Validate overlays is a list of overlay spec dicts
3. Each overlay spec must have at least: preset, text, start, end

### IMPLEMENT
1. Build combined FFmpeg filter chain from all overlay specs
2. Each overlay maps to a drawtext filter via preset template
3. Multiple overlays are chained with commas in a single -vf pass
4. Apply filters to input video in a single FFmpeg invocation

### VERIFY (After)
1. Output video exists and is playable
2. Duration preserved (within 0.5s tolerance)
3. Resolution preserved
4. QA checks pass

## Presets
- `lower_third`: Animated lower-third title bar with background box
- `title_card`: Centered title text with timed display
- `scroll_text`: Text scrolling from bottom to top
- `corner_badge`: Small badge in top-right corner with background
- `countdown`: Countdown timer overlay

## Parameters (per overlay spec)
- `preset`: One of the preset names above (required)
- `text`: Text to display (required)
- `start`: Start time in seconds (required)
- `end`: End time in seconds (required)
- `fontsize`: Font size in pixels (default: 48)
- `color`: Font color (default: white)
- `bg_color`: Background box color, for presets that use it (default: black@0.7)
- `speed`: Scroll speed for scroll_text preset (default: 80)
- `total`: Total seconds for countdown preset (default: end - start)

## Example
```bash
# Add a lower third
python services/skill_animation.py --input video.mp4 --output out.mp4 \
  --overlay '{"preset":"lower_third","text":"John Doe - CEO","start":2,"end":8,"fontsize":36,"color":"white","bg_color":"black@0.7"}'

# Add multiple overlays
python services/skill_animation.py --input video.mp4 --output out.mp4 \
  --overlay '{"preset":"title_card","text":"Welcome","start":0,"end":3}' \
  --overlay '{"preset":"corner_badge","text":"LIVE","start":0,"end":60}'
```
