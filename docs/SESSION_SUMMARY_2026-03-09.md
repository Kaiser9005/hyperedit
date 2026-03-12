# Session Summary — 2026-03-09

## Objective
Upgrade the HyperEdit/ClipWise video production system with kie.ai unified API integration for AI image/video generation, scroll-driven websites, HTML5 ads, and landing pages.

## Context
- **Project**: HyperEdit AI (`/Users/cherylmaevahfodjo/hyperedit-ai/`)
- **Client**: FOFAL (agricultural company, Cameroon)
- **Product**: TerraFlow ERP
- **ERP (deployed)**: https://modules-rh-authentification-expert.vercel.app
- **FOFAL website**: Not yet deployed — still in development. Website builders are now production-ready.
- **Existing pipeline**: Storyboard → Image resolution → Ken Burns → Voiceover → Transitions → Watermark → QA verification

---

## What Was Built (8 New Services)

### Core API Integration
| Service | File | Purpose |
|---------|------|---------|
| KieClient | `services/kie_client.py` | Unified async API client for kie.ai (create → poll → download) |
| KieImageGenerator | `services/skill_kie_image.py` | Nano Banana Pro image generation (up to 4K, ~$0.03/image) |
| KieVideoGenerator | `services/skill_kie_video.py` | Kling 3.0 video generation (3-15s, multi-shot, native audio) |

### Marketing Asset Builders
| Service | File | Purpose |
|---------|------|---------|
| AdsBuilder | `services/ads_builder.py` | HTML5 + static ads for Meta/Google/LinkedIn (5 essential sizes) |
| ScrollSiteBuilder | `services/scroll_site_builder.py` | Apple-style scroll-driven canvas websites from video |
| LandingPageBuilder | `services/landing_page_builder.py` | Single-file responsive landing pages |
| FFmpegWebOps | `services/ffmpeg_web_ops.py` | WebP frames, VP9, posters, GIFs, sprite sheets |
| AdSpecs | `services/ad_specs.py` | Platform size registries, clicktag patterns, limits |

### Skill Documentation
| File | Purpose |
|------|---------|
| `.agents/skills/creative-campaign/SKILL.md` | Skill manifest for Claude Code discovery |

---

## What Was Modified (3 Existing Files)

### `services/fofal_assembler.py` (Main Orchestrator)
- **+2 scene types**: `"ai_video"` (Kling 3.0 text-to-video), `"ai_image_to_video"` (image → Kling 3.0)
- **+`generate_marketing` flag**: When True, auto-generates scroll site, ads, landing page, web MP4, preview GIF
- **+`_generate_marketing_assets()` method**: Full post-production marketing pipeline
- **Lazy initialization**: All new services initialized only when needed (no crash if `KIE_API_KEY` absent)
- **Zero regression**: All existing scene types (`branding`, `ui_recording`) unchanged

### `services/image_intelligence.py` (Image Resolver)
- **+kie.ai Nano Banana Pro** added to resolution chain (position 3, between Pexels and fal.ai)
- **Chain**: Brand assets → Cache → Unsplash → Pexels → **kie.ai** → fal.ai → Last resort
- **Caching**: Generated images cached in `assets/cache/{category}/` to avoid re-generation

### `services/ffmpeg_web_ops.py` (Web FFmpeg Ops)
- **Bug fix**: WebP frame extraction used `libwebp_anim` (animated) instead of `libwebp` (static)
- **Fix**: Explicit `-c:v libwebp` + `-quality` parameter for all WebP extraction methods

---

## Bugs Found & Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| WebP extraction: 1 frame instead of 60 | FFmpeg auto-selected `libwebp_anim` encoder | Force `-c:v libwebp` for static WebP |
| Kling 3.0: `AttributeError: NoneType` | API returned `{"data": null}` on error | Added null guard before accessing `data` dict |
| Kling 3.0: 422 `multi_shots cannot be empty` | `multi_shots` only set when True | Always set `multi_shots` explicitly (even False) |
| Kling 3.0: 402 Credits insufficient | Account balance too low | User topped up credits |
| HTML5 ad: broken `style` attribute | Double quotes inside double quotes | Changed to single quotes for `url('bg.jpg')` |
| Nano Banana Pro: TimeoutError at 120s | Image still in queue after 2min | Increased default `max_wait` to 300s |

---

## Test Results (Full E2E Workflow)

| Step | Service | Result | Details |
|------|---------|--------|---------|
| 1. Image generation | Nano Banana Pro | PASS | 8.9 MB, 2752x1536, ~3min |
| 2. Video generation | **Kling 3.0** | PASS | 9.1 MB, 5s, 1280x720, 428s |
| 3. Frame extraction | FFmpegWebOps | PASS | 60 WebP frames, avg 99 KB each |
| 4. Scroll site | ScrollSiteBuilder | PASS | 65 files, 5.9 MB |
| 5. HTML5 ads | AdsBuilder | PASS | 6 variants, 32 KB (< 150 KB GDN limit) |
| 6. Landing page | LandingPageBuilder | PASS | 6.3 KB single-file HTML |
| 7. Preview GIF | FFmpegWebOps | PASS | 6.3 MB (480px, 12fps) |
| 8. Web MP4 | FFmpegWebOps | PASS | 1.3 MB (H.264 faststart) |

**All 8 steps PASS. Zero regressions.**

---

## Architecture After Upgrade

```
Storyboard JSON
     |
FofalVideoAssembler.assemble(generate_marketing=True)
     |-- Per scene:
     |   |-- "branding"           -> ImageIntelligence -> Ken Burns
     |   |-- "ui_recording"       -> Screen recording (existing)
     |   |-- "ai_video"           -> Kling 3.0 text-to-video (NEW)
     |   |-- "ai_image_to_video"  -> Image -> Kling 3.0 (NEW)
     |-- Voiceover (ElevenLabs TTS)
     |-- Merge narration + video
     |-- Transitions (crossfade)
     |-- Watermark
     |-- E2E Verification (>= 7.0/10)
     |-- Marketing Assets (NEW, optional):
         |-- Web MP4 (H.264 faststart)
         |-- Preview GIF
         |-- Scroll Site (Apple-style canvas, 60 frames)
         |-- HTML5 Ads (6 variants, 5 essential sizes)
         |-- Landing Page (responsive, inline CSS/JS)
```

### Image Resolution Chain (Updated)
```
1. Brand assets (curated: assets/brand/fofal/)
2. Cache (previously downloaded: assets/cache/)
3. Unsplash API (stock photos)
4. Pexels API (stock photos)
5. kie.ai Nano Banana Pro (AI generation, up to 4K)  <-- NEW
6. fal.ai FLUX Schnell (AI generation, fast fallback)
7. Last resort (any brand asset)
```

---

## Existing FOFAL Assets

| Asset | Location | Status |
|-------|----------|--------|
| Brand images (8) | `assets/brand/fofal/` | hero-bg, products, team, plantation |
| Presentation video | `output_videos/fofal_assembly/` | 33 MB, 5 scenes, Ken Burns + narration |
| ERP recordings (39) | `assets/erp_recordings/` | All ERP module demos |
| Storyboard | `templates/storyboards/fofal_presentation.json` | 5 scenes, 2min target |
| Brand config | `templates/brands/fofal.json` | Colors, fonts, watermark |
| Tutorial storyboards (13) | `templates/storyboards/` | Per-module ERP tutorials |

---

## KIE API Key & Costs

- **Key**: Configured in `.env` as `KIE_API_KEY`
- **Image (Nano Banana Pro)**: ~$0.03/image
- **Video (Kling 3.0 std)**: ~$0.125/5s
- **Video (Kling 3.0 pro)**: ~$0.25/5s
- **Test consumption this session**: ~$0.50 (1 image + 2 video attempts)

---

## Test Outputs

All test outputs saved to `/tmp/kie_workflow/`:
- `frames/` — 60 WebP frames
- `scroll_site/` — Complete scroll-driven website
- `ads/` — HTML5 + static ad variants
- `landing/` — Marketing landing page
- `hero_web.mp4` — Web-optimized video
- `preview.gif` — Animated preview

Video: `/tmp/kie_test_kling3.mp4` (Kling 3.0, 5s, 9.1 MB)
Image: `/tmp/kie_test_image.png` (Nano Banana Pro, 8.9 MB)

---

## Next Steps

1. **Build FOFAL website** — Use ScrollSiteBuilder + LandingPageBuilder with brand assets and AI-generated video to create the actual client website
2. **Deploy to Vercel/Framer** — Website needs a production URL
3. **Storyboard with AI scenes** — Create storyboards using `"ai_video"` scene type for richer visuals than Ken Burns
4. **Wire into fofal_assembler CLI** — Enable `generate_marketing=True` from command line
5. **Image-to-video workflow** — Upload start frames to get public URLs for Kling 3.0 I2V
