"""Landing Page Builder — generates standalone marketing landing pages.

Produces a complete single-page site with:
  - Hero section with AI-generated background
  - Feature sections with scroll animations
  - CTA sections
  - Responsive design (mobile-first)
  - CSS-only animations (no JS dependencies for core layout)

Output: index.html + inline CSS/JS (single file for easy deployment).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


DEFAULT_LANDING_CONFIG = {
    "title": "TerraFlow",
    "tagline": "L'ERP Agricole Intelligent pour l'Afrique",
    "description": "Gérez votre exploitation agricole de A à Z : RH, comptabilité OHADA, production, ventes — tout en un.",
    "primary_color": "#166534",
    "secondary_color": "#D97706",
    "bg_dark": "#0a0a0a",
    "text_light": "#ffffff",
    "cta_primary": "Demander une Démo",
    "cta_secondary": "Voir les Tarifs",
    "cta_url": "#contact",
}


class LandingPageBuilder:
    """Generate standalone marketing landing pages.

    Usage:
        builder = LandingPageBuilder()
        builder.build(
            output_path=Path("dist/landing/index.html"),
            hero_image_url="https://...",
            features=[
                {"title": "Gestion RH", "desc": "...", "icon": "users"},
                {"title": "Comptabilité OHADA", "desc": "...", "icon": "calculator"},
            ],
        )
    """

    def build(
        self,
        output_path: Path,
        config: Optional[dict] = None,
        hero_image_url: Optional[str] = None,
        hero_video_url: Optional[str] = None,
        features: Optional[list[dict]] = None,
        testimonials: Optional[list[dict]] = None,
        stats: Optional[list[dict]] = None,
    ) -> Path:
        """Build a complete landing page.

        Args:
            output_path: Where to write the HTML file.
            config: Brand/content configuration.
            hero_image_url: Background image URL for hero.
            hero_video_url: Background video URL for hero (takes priority).
            features: List of feature sections.
            testimonials: List of testimonials.
            stats: List of stat items (number + label).

        Returns:
            Path to the generated HTML file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cfg = {**DEFAULT_LANDING_CONFIG, **(config or {})}
        features = features or []
        testimonials = testimonials or []
        stats = stats or []

        # Build sections
        hero_html = self._build_hero(cfg, hero_image_url, hero_video_url)
        stats_html = self._build_stats(stats, cfg) if stats else ""
        features_html = self._build_features(features, cfg)
        testimonials_html = self._build_testimonials(testimonials, cfg) if testimonials else ""
        cta_html = self._build_cta(cfg)
        footer_html = self._build_footer(cfg)

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{cfg['title']} — {cfg['tagline']}</title>
  <meta name="description" content="{cfg['description']}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>{self._build_css(cfg)}</style>
</head>
<body>
{hero_html}
{stats_html}
{features_html}
{testimonials_html}
{cta_html}
{footer_html}
  <script>{self._build_js()}</script>
</body>
</html>"""

        output_path.write_text(html, encoding="utf-8")
        size_kb = output_path.stat().st_size / 1024
        logger.info("Landing page built: %s (%.0f KB)", output_path, size_kb)
        return output_path

    def _build_hero(self, cfg: dict, img_url: Optional[str], video_url: Optional[str]) -> str:
        bg = ""
        if video_url:
            bg = f"""<video class="hero-bg-video" autoplay muted loop playsinline>
        <source src="{video_url}" type="video/mp4">
      </video>"""
        elif img_url:
            bg = f'<div class="hero-bg-image" style="background-image:url({img_url})"></div>'

        return f"""  <section class="hero">
      {bg}
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <h1 class="hero-title animate-in">{cfg['title']}</h1>
        <p class="hero-tagline animate-in" style="--delay:0.2s">{cfg['tagline']}</p>
        <p class="hero-desc animate-in" style="--delay:0.4s">{cfg['description']}</p>
        <div class="hero-ctas animate-in" style="--delay:0.6s">
          <a href="{cfg['cta_url']}" class="btn btn-primary">{cfg['cta_primary']}</a>
          <a href="#features" class="btn btn-secondary">{cfg['cta_secondary']}</a>
        </div>
      </div>
    </section>"""

    def _build_stats(self, stats: list[dict], cfg: dict) -> str:
        items = "".join(
            f'<div class="stat-item scroll-reveal"><span class="stat-number">{s["value"]}</span>'
            f'<span class="stat-label">{s["label"]}</span></div>'
            for s in stats
        )
        return f"""  <section class="stats">{items}</section>"""

    def _build_features(self, features: list[dict], cfg: dict) -> str:
        items = ""
        for i, f in enumerate(features):
            direction = "left" if i % 2 == 0 else "right"
            items += f"""
      <div class="feature scroll-reveal" data-direction="{direction}">
        <div class="feature-text">
          <h3>{f.get('title', '')}</h3>
          <p>{f.get('desc', '')}</p>
        </div>
      </div>"""
        return f"""  <section id="features" class="features">{items}\n    </section>"""

    def _build_testimonials(self, testimonials: list[dict], cfg: dict) -> str:
        items = "".join(
            f'<div class="testimonial scroll-reveal">'
            f'<blockquote>"{t["quote"]}"</blockquote>'
            f'<cite>— {t.get("name", "")}, {t.get("role", "")}</cite></div>'
            for t in testimonials
        )
        return f"""  <section class="testimonials">{items}</section>"""

    def _build_cta(self, cfg: dict) -> str:
        return f"""  <section id="contact" class="cta-section">
      <div class="cta-content scroll-reveal">
        <h2>Prêt à transformer votre exploitation ?</h2>
        <a href="{cfg['cta_url']}" class="btn btn-primary btn-lg">{cfg['cta_primary']}</a>
      </div>
    </section>"""

    def _build_footer(self, cfg: dict) -> str:
        return f"""  <footer>
      <p>&copy; 2026 {cfg['title']}. Tous droits réservés.</p>
    </footer>"""

    def _build_css(self, cfg: dict) -> str:
        return f"""
:root{{--primary:{cfg['primary_color']};--secondary:{cfg['secondary_color']};--bg:{cfg['bg_dark']};--text:{cfg['text_light']};}}
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth;font-family:'Inter',system-ui,sans-serif;color:var(--text);background:var(--bg)}}
body{{overflow-x:hidden}}

.hero{{position:relative;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.hero-bg-video,.hero-bg-image{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.hero-bg-image{{background-size:cover;background-position:center}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,0.5),rgba(0,0,0,0.8))}}
.hero-content{{position:relative;z-index:2;text-align:center;padding:2rem;max-width:800px}}
.hero-title{{font-size:clamp(2.5rem,8vw,5rem);font-weight:800;letter-spacing:-0.03em;line-height:1.1}}
.hero-tagline{{font-size:clamp(1.1rem,2.5vw,1.5rem);margin-top:1rem;color:var(--secondary);font-weight:600}}
.hero-desc{{font-size:1rem;margin-top:1rem;opacity:0.8;line-height:1.6;max-width:600px;margin-left:auto;margin-right:auto}}
.hero-ctas{{margin-top:2rem;display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}}

.btn{{display:inline-block;padding:0.875rem 2rem;border-radius:50px;text-decoration:none;font-weight:700;font-size:1rem;transition:transform 0.3s,box-shadow 0.3s}}
.btn-primary{{background:var(--primary);color:white}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 25px rgba(22,101,52,0.4)}}
.btn-secondary{{background:transparent;color:white;border:2px solid rgba(255,255,255,0.3)}}
.btn-secondary:hover{{border-color:white;transform:translateY(-2px)}}
.btn-lg{{padding:1.1rem 2.5rem;font-size:1.1rem}}

.animate-in{{opacity:0;transform:translateY(30px);animation:fadeUp 0.8s ease-out forwards;animation-delay:var(--delay,0s)}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(30px)}}to{{opacity:1;transform:translateY(0)}}}}

.stats{{display:flex;justify-content:center;gap:3rem;padding:4rem 2rem;flex-wrap:wrap}}
.stat-item{{text-align:center}}
.stat-number{{display:block;font-size:2.5rem;font-weight:800;color:var(--secondary)}}
.stat-label{{display:block;font-size:0.9rem;opacity:0.7;margin-top:0.25rem}}

.features{{max-width:900px;margin:0 auto;padding:4rem 2rem}}
.feature{{padding:3rem 0}}
.feature h3{{font-size:1.5rem;font-weight:700;margin-bottom:1rem;color:var(--secondary)}}
.feature p{{font-size:1rem;line-height:1.8;opacity:0.8}}

.testimonials{{padding:4rem 2rem;max-width:800px;margin:0 auto}}
.testimonial{{padding:2rem 0;border-bottom:1px solid rgba(255,255,255,0.1)}}
.testimonial blockquote{{font-size:1.1rem;font-style:italic;line-height:1.7;opacity:0.9}}
.testimonial cite{{display:block;margin-top:1rem;font-size:0.9rem;color:var(--secondary)}}

.cta-section{{text-align:center;padding:6rem 2rem;background:linear-gradient(135deg,var(--primary),var(--secondary))}}
.cta-section h2{{font-size:clamp(1.5rem,4vw,2.5rem);margin-bottom:2rem}}

footer{{text-align:center;padding:2rem;opacity:0.5;font-size:0.85rem}}

.scroll-reveal{{opacity:0;transform:translateY(40px);transition:opacity 0.8s ease,transform 0.8s ease}}
.scroll-reveal.visible{{opacity:1;transform:translateY(0)}}

@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}}}
@media(max-width:768px){{.stats{{gap:1.5rem}}.stat-number{{font-size:2rem}}.hero-ctas{{flex-direction:column;align-items:center}}}}
"""

    def _build_js(self) -> str:
        return """
const io=new IntersectionObserver(e=>{e.forEach(el=>{if(el.isIntersecting)el.target.classList.add('visible')})},{threshold:0.15});
document.querySelectorAll('.scroll-reveal').forEach(el=>io.observe(el));
"""
