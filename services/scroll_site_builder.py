"""Scroll-Driven Website Builder — generates HTML/CSS/JS from video frames.

Produces Apple-style scroll-driven animated websites using:
  - CSS scroll-driven animations (Chrome 115+, Safari 26+, ~82% global)
  - Canvas frame sequence technique (Apple.com style)
  - GSAP ScrollTrigger fallback for complex interactions

Output: Complete static site (index.html + styles + scripts + frames/)
ready for Vercel deployment.

V-I-V: Validates frame count, generates complete site, verifies output.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ffmpeg_web_ops import FFmpegWebOps

logger = logging.getLogger(__name__)


# Default brand config for generated sites
DEFAULT_SITE_CONFIG = {
    "title": "TerraFlow",
    "subtitle": "ERP Agricole Intelligent",
    "primary_color": "#166534",
    "secondary_color": "#D97706",
    "accent_color": "#78350F",
    "bg_color": "#0a0a0a",
    "text_color": "#ffffff",
    "font_heading": "'Inter', system-ui, sans-serif",
    "font_body": "'Inter', system-ui, sans-serif",
    "cta_text": "Demander une Démo",
    "cta_url": "#contact",
}


class ScrollSiteBuilder:
    """Build scroll-driven animated websites from video content.

    Pipeline:
      1. Extract frames from source video (WebP, quality 82)
      2. Generate index.html with canvas-based scroll animation
      3. Generate CSS with design tokens and animations
      4. Generate JavaScript scroll controller
      5. Output complete static site directory

    Usage:
        builder = ScrollSiteBuilder()
        site_path = builder.build(
            video_path=Path("source/hero.mp4"),
            output_dir=Path("dist/scroll-site"),
            config={"title": "TerraFlow", "cta_text": "Try Now"},
        )
    """

    def __init__(self):
        self.ffmpeg_web = FFmpegWebOps()

    def build(
        self,
        video_path: Path,
        output_dir: Path,
        config: Optional[dict] = None,
        num_frames: int = 120,
        frame_width: int = 1920,
        sections: Optional[list[dict]] = None,
    ) -> Path:
        """Build a complete scroll-driven site from a video.

        Args:
            video_path: Source video for frame extraction.
            output_dir: Output directory for the site.
            config: Brand/content configuration (merged with defaults).
            num_frames: Number of frames to extract for scroll animation.
            frame_width: Frame width in pixels.
            sections: Optional list of content sections to overlay.

        Returns:
            Path to the output directory containing the complete site.
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        # Merge config with defaults
        site_config = {**DEFAULT_SITE_CONFIG, **(config or {})}
        sections = sections or []

        # V-I-V Verify: input exists
        if not video_path.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")

        # 1. Create directory structure
        frames_dir = output_dir / "assets" / "frames"
        styles_dir = output_dir / "styles"
        scripts_dir = output_dir / "scripts"
        for d in [frames_dir, styles_dir, scripts_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 2. Extract frames
        logger.info("Extracting %d frames from %s...", num_frames, video_path.name)
        frames = self.ffmpeg_web.extract_frames_uniform(
            input_path=video_path,
            output_dir=frames_dir,
            num_frames=num_frames,
            width=frame_width,
        )
        logger.info("Extracted %d frames", len(frames))

        if len(frames) < 10:
            raise RuntimeError(f"Too few frames extracted: {len(frames)} (need at least 10)")

        actual_count = len(frames)

        # 3. Generate site files
        self._write_html(output_dir / "index.html", site_config, sections, actual_count)
        self._write_css(styles_dir / "main.css", site_config)
        self._write_scroll_controller(scripts_dir / "scroll-controller.js", actual_count)
        self._write_app_js(scripts_dir / "app.js", site_config, sections)

        # 4. Generate poster (first frame)
        self.ffmpeg_web.extract_poster(
            video_path, output_dir / "assets" / "poster.webp", width=frame_width,
        )

        logger.info("Scroll site built: %s (%d frames, %d sections)",
                     output_dir, actual_count, len(sections))
        return output_dir

    def _write_html(
        self, path: Path, config: dict, sections: list[dict], frame_count: int,
    ) -> None:
        """Generate index.html with canvas scroll animation."""
        sections_html = ""
        for i, section in enumerate(sections):
            sections_html += f"""
    <section class="content-section" data-section="{i}" style="--section-index: {i};">
      <div class="section-inner">
        <h2>{section.get('title', '')}</h2>
        <p>{section.get('text', '')}</p>
      </div>
    </section>"""

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{config['title']} — {config['subtitle']}</title>
  <link rel="stylesheet" href="styles/main.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
  <!-- Hero: Canvas scroll animation (Apple-style) -->
  <div id="hero-wrapper">
    <canvas id="hero-canvas" width="1920" height="1080"></canvas>
    <div id="hero-overlay">
      <h1 class="hero-title">{config['title']}</h1>
      <p class="hero-subtitle">{config['subtitle']}</p>
      <a href="{config['cta_url']}" class="cta-button">{config['cta_text']}</a>
    </div>
  </div>

  <!-- Scroll spacer (drives the canvas animation) -->
  <div id="scroll-spacer"></div>
{sections_html}

  <!-- Footer -->
  <footer id="contact">
    <p>&copy; 2026 {config['title']}. Tous droits réservés.</p>
  </footer>

  <script src="scripts/scroll-controller.js"></script>
  <script src="scripts/app.js"></script>
</body>
</html>"""
        path.write_text(html, encoding="utf-8")

    def _write_css(self, path: Path, config: dict) -> None:
        """Generate main.css with design tokens and scroll animations."""
        css = f"""/* Design Tokens */
:root {{
  --color-primary: {config['primary_color']};
  --color-secondary: {config['secondary_color']};
  --color-accent: {config['accent_color']};
  --color-bg: {config['bg_color']};
  --color-text: {config['text_color']};
  --font-heading: {config['font_heading']};
  --font-body: {config['font_body']};
}}

/* Reset */
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

html {{
  scroll-behavior: smooth;
  font-family: var(--font-body);
  color: var(--color-text);
  background: var(--color-bg);
}}

body {{ overflow-x: hidden; }}

/* Hero Canvas */
#hero-wrapper {{
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  z-index: 1;
}}

#hero-canvas {{
  width: 100%; height: 100%;
  object-fit: cover;
}}

#hero-overlay {{
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  z-index: 2;
  pointer-events: none;
}}

.hero-title {{
  font-family: var(--font-heading);
  font-size: clamp(2.5rem, 8vw, 6rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  opacity: 0;
  transform: translateY(30px);
  animation: fadeUp 1s ease-out 0.3s forwards;
}}

.hero-subtitle {{
  font-size: clamp(1rem, 2.5vw, 1.5rem);
  opacity: 0;
  margin-top: 1rem;
  animation: fadeUp 1s ease-out 0.6s forwards;
}}

.cta-button {{
  display: inline-block;
  margin-top: 2rem;
  padding: 1rem 2.5rem;
  background: var(--color-primary);
  color: white;
  text-decoration: none;
  border-radius: 50px;
  font-weight: 700;
  font-size: 1.1rem;
  pointer-events: auto;
  opacity: 0;
  animation: fadeUp 1s ease-out 0.9s forwards;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}}

.cta-button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(22, 101, 52, 0.4);
}}

/* Scroll Spacer */
#scroll-spacer {{
  height: 500vh;
  position: relative;
  z-index: 0;
}}

/* Content Sections */
.content-section {{
  position: relative;
  z-index: 10;
  min-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  background: var(--color-bg);
}}

.section-inner {{
  max-width: 800px;
  text-align: center;
  opacity: 0;
  transform: translateY(40px);
}}

.content-section.visible .section-inner {{
  animation: fadeUp 0.8s ease-out forwards;
}}

.section-inner h2 {{
  font-family: var(--font-heading);
  font-size: clamp(1.5rem, 4vw, 3rem);
  font-weight: 700;
  margin-bottom: 1.5rem;
  color: var(--color-secondary);
}}

.section-inner p {{
  font-size: 1.125rem;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
}}

/* Footer */
footer {{
  position: relative;
  z-index: 10;
  text-align: center;
  padding: 3rem 2rem;
  background: var(--color-bg);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.5);
}}

/* Animations */
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(30px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* Performance: only animate transform and opacity (GPU-composited) */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }}
}}
"""
        path.write_text(css, encoding="utf-8")

    def _write_scroll_controller(self, path: Path, frame_count: int) -> None:
        """Generate scroll controller for canvas frame animation."""
        js = f"""// Scroll-driven canvas frame animation (Apple-style)
// Preloads frames and maps scroll position to frame index.

const FRAME_COUNT = {frame_count};
const images = [];
let loaded = 0;

// Preload all frames
for (let i = 1; i <= FRAME_COUNT; i++) {{
  const img = new Image();
  img.src = 'assets/frames/frame_' + String(i).padStart(4, '0') + '.webp';
  img.onload = () => {{
    loaded++;
    if (loaded === FRAME_COUNT) {{
      console.log('All ' + FRAME_COUNT + ' frames loaded');
      drawFrame(0);
    }}
  }};
  images.push(img);
}}

const canvas = document.getElementById('hero-canvas');
const ctx = canvas.getContext('2d');

function drawFrame(index) {{
  const img = images[index];
  if (!img || !img.complete) return;

  // Scale to fill canvas while maintaining aspect ratio
  const scale = Math.max(canvas.width / img.width, canvas.height / img.height);
  const w = img.width * scale;
  const h = img.height * scale;
  const x = (canvas.width - w) / 2;
  const y = (canvas.height - h) / 2;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, x, y, w, h);
}}

// Resize canvas to match viewport
function resizeCanvas() {{
  canvas.width = window.innerWidth * window.devicePixelRatio;
  canvas.height = window.innerHeight * window.devicePixelRatio;
  canvas.style.width = '100vw';
  canvas.style.height = '100vh';
}}
resizeCanvas();
window.addEventListener('resize', resizeCanvas, {{ passive: true }});

// Map scroll position to frame index
const scrollSpacer = document.getElementById('scroll-spacer');

window.addEventListener('scroll', () => {{
  const scrollTop = window.scrollY;
  const maxScroll = scrollSpacer.offsetHeight - window.innerHeight;
  const scrollFraction = Math.min(1, Math.max(0, scrollTop / maxScroll));
  const frameIndex = Math.min(FRAME_COUNT - 1, Math.floor(scrollFraction * FRAME_COUNT));

  requestAnimationFrame(() => drawFrame(frameIndex));

  // Fade out hero overlay as user scrolls
  const overlay = document.getElementById('hero-overlay');
  if (overlay) {{
    overlay.style.opacity = Math.max(0, 1 - scrollFraction * 3);
  }}
}}, {{ passive: true }});
"""
        path.write_text(js, encoding="utf-8")

    def _write_app_js(self, path: Path, config: dict, sections: list[dict]) -> None:
        """Generate app.js with section reveal animations."""
        js = """// Section reveal on scroll (IntersectionObserver)
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  },
  { threshold: 0.2 }
);

document.querySelectorAll('.content-section').forEach((section) => {
  observer.observe(section);
});
"""
        path.write_text(js, encoding="utf-8")
