---
name: creative-campaign
description: Generate animated websites, ads, landing pages, and video from AI images/video via kie.ai
keywords:
  - website
  - scroll
  - ads
  - landing page
  - kie
  - image generation
  - video generation
  - banner
  - campaign
  - marketing
  - meta
  - google
  - linkedin
  - html5
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
---

# Creative Campaign — Animated Sites, Ads & Landing Pages

## Capabilities

1. **AI Image Generation** (kie.ai Nano Banana Pro)
   - Text-to-image, up to 4K resolution
   - All aspect ratios: 1:1, 16:9, 9:16, 3:2, 4:5
   - ~$0.03/image, results in ~2-3 minutes

2. **AI Video Generation** (kie.ai Kling 3.0)
   - Text-to-video and image-to-video
   - 3-15 seconds, native audio, multi-shot
   - Pro mode for quality, std for speed

3. **Scroll-Driven Websites** (Apple-style)
   - Canvas frame sequence from video
   - WebP frames at quality 82 (best size/quality ratio)
   - CSS scroll-driven animations + IntersectionObserver

4. **HTML5 Ads** (Meta/Google/LinkedIn)
   - 5 essential cross-platform sizes
   - Clicktag patterns per platform
   - ≤150KB ZIP for Google GDN
   - 30s animation auto-stop

5. **Landing Pages**
   - Single-file HTML with inline CSS/JS
   - Hero video/image, features, CTA
   - Responsive, accessible, prefers-reduced-motion

## Services (in services/)

| File | Purpose |
|------|---------|
| `kie_client.py` | Unified async API client (create → poll → download) |
| `skill_kie_image.py` | Nano Banana image generation |
| `skill_kie_video.py` | Kling 3.0 video generation |
| `ad_specs.py` | Platform sizes, limits, clicktag patterns |
| `ffmpeg_web_ops.py` | WebP frames, VP9, posters, GIFs |
| `scroll_site_builder.py` | Canvas scroll site from video |
| `ads_builder.py` | Static + HTML5 ad builder |
| `landing_page_builder.py` | Marketing landing page generator |

## Quick Start

```python
# Image generation
from skill_kie_image import KieImageGenerator
gen = KieImageGenerator()
result = gen.generate(prompt="...", output_path=Path("hero.png"))

# Video generation
from skill_kie_video import KieVideoGenerator
gen = KieVideoGenerator()
result = gen.generate(prompt="...", output_path=Path("hero.mp4"))

# Scroll site from video
from scroll_site_builder import ScrollSiteBuilder
builder = ScrollSiteBuilder()
builder.build(video_path=Path("hero.mp4"), output_dir=Path("dist/site"))

# HTML5 ads
from ads_builder import AdsBuilder
builder = AdsBuilder()
builder.build_html5_ad(output_dir=Path("dist/ads/300x250"), width=300, height=250)

# Landing page
from landing_page_builder import LandingPageBuilder
builder = LandingPageBuilder()
builder.build(output_path=Path("dist/landing/index.html"), hero_image_url="...")
```

## Full Production Workflow

1. **Generate image** → Nano Banana Pro (start_frame for video)
2. **Generate video** → Kling 3.0 (start_frame + prompt → video)
3. **Extract frames** → FFmpeg WebP (video → 120 scroll frames)
4. **Build scroll site** → HTML/CSS/JS with canvas animation
5. **Build ads** → Static images + HTML5 in all platform sizes
6. **Build landing page** → Single-file responsive HTML
7. **Deploy** → Vercel via GitHub push

## Environment

Requires `KIE_API_KEY` in `.env` or environment.
FFmpeg must be installed locally for frame extraction and optimization.
