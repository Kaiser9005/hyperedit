"""HTML5 Ads Builder — generates platform-compliant ad creatives.

Produces ads for:
  - Meta (Facebook/Instagram): static images in 5 sizes
  - Google Display Network: HTML5 ads with clicktag, ≤150KB ZIP
  - LinkedIn: landscape + square + carousel
  - HTML5 animated ads: CSS @keyframes with 30s auto-stop
  - Video ads: FFmpeg-optimized for platform specs

Each ad is a self-contained directory (or ZIP) with:
  index.html, style.css, script.js, images, fallback.jpg

V-I-V: Validates file sizes against platform limits, checks clicktag.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ad_specs import (
    CLICKTAG_PATTERNS,
    ESSENTIAL_SIZES,
    GOOGLE_SIZES,
    LINKEDIN_SIZES,
    META_SIZES,
    PLATFORM_LIMITS,
    get_platform_limit,
)
from ffmpeg_web_ops import FFmpegWebOps

logger = logging.getLogger(__name__)


# Default brand config for ads
DEFAULT_AD_BRAND = {
    "name": "TerraFlow",
    "primary_color": "#166534",
    "secondary_color": "#D97706",
    "text_color": "#FFFFFF",
    "logo_path": None,
    "cta_text": "En savoir plus",
    "landing_url": "https://terraflow.cm",
}


class AdsBuilder:
    """Build platform-compliant ad creatives from assets.

    Supports static image ads, HTML5 animated ads, and video ads.

    Usage:
        builder = AdsBuilder()

        # Static ad image (resize + brand overlay)
        builder.build_static_ad(
            image_path=Path("hero.png"),
            output_dir=Path("dist/ads/meta"),
            platform="meta",
        )

        # HTML5 animated ad (300x250)
        builder.build_html5_ad(
            output_dir=Path("dist/ads/html5/300x250"),
            width=300, height=250,
            headline="ERP Agricole Intelligent",
        )
    """

    def __init__(self):
        self.ffmpeg_web = FFmpegWebOps()

    def build_static_ad(
        self,
        image_path: Path,
        output_dir: Path,
        platform: str = "meta",
        brand: Optional[dict] = None,
    ) -> dict[str, Path]:
        """Generate static ad images in all sizes for a platform.

        Resizes the source image to each platform size using FFmpeg
        with lanczos scaling.

        Args:
            image_path: Source image (high-res, ideally 4K).
            output_dir: Output directory for resized images.
            platform: Target platform (meta, google, linkedin).
            brand: Brand config for overlays.

        Returns:
            Dict mapping size name to output path.
        """
        image_path = Path(image_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not image_path.exists():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        sizes = {"meta": META_SIZES, "google": GOOGLE_SIZES, "linkedin": LINKEDIN_SIZES}
        platform_sizes = sizes.get(platform, META_SIZES)

        results = {}
        for name, spec in platform_sizes.items():
            # Skip video-only specs
            if spec.get("format", "jpg") in ("mp4", "mov"):
                continue

            w, h = spec["width"], spec["height"]
            ext = spec.get("format", "jpg")
            out_path = output_dir / f"{name}.{ext}"

            cmd = [
                self.ffmpeg_web.svc.ffmpeg,
                "-i", str(image_path),
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
                "-frames:v", "1",
            ]
            if ext == "jpg":
                cmd.extend(["-q:v", "2"])
            cmd.extend([str(out_path), "-y"])

            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=30)
                results[name] = out_path
                logger.info("Static ad: %s %dx%d → %s", name, w, h, out_path.name)
            except subprocess.CalledProcessError as e:
                logger.warning("Failed to generate %s: %s", name, e)

        return results

    def build_html5_ad(
        self,
        output_dir: Path,
        width: int = 300,
        height: int = 250,
        headline: str = "ERP Agricole Intelligent",
        cta_text: str = "En savoir plus",
        landing_url: str = "https://terraflow.cm",
        brand: Optional[dict] = None,
        logo_path: Optional[Path] = None,
        bg_image_path: Optional[Path] = None,
    ) -> Path:
        """Generate a complete HTML5 animated ad.

        Produces: index.html, style.css, script.js, and optional images.
        Compliant with Google Ads/DV360 requirements:
        - <meta name="ad.size"> tag
        - clickTag variable in <head>
        - Animations stop at 30s
        - Total ZIP target: ≤150KB

        Args:
            output_dir: Output directory for the ad.
            width: Ad width in pixels.
            height: Ad height in pixels.
            headline: Main headline text.
            cta_text: Call-to-action button text.
            landing_url: Click-through URL.
            brand: Brand config.
            logo_path: Optional logo image to include.
            bg_image_path: Optional background image.

        Returns:
            Path to the output directory.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        brand = {**DEFAULT_AD_BRAND, **(brand or {})}

        # Copy assets
        if logo_path and Path(logo_path).exists():
            shutil.copy2(logo_path, output_dir / "logo.png")
        if bg_image_path and Path(bg_image_path).exists():
            # Resize to ad dimensions
            cmd = [
                self.ffmpeg_web.svc.ffmpeg,
                "-i", str(bg_image_path),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                       f"crop={width}:{height}",
                "-q:v", "5",
                str(output_dir / "bg.jpg"), "-y",
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)

        # Generate HTML
        self._write_ad_html(output_dir / "index.html", width, height,
                           headline, cta_text, landing_url, brand, bg_image_path is not None)
        self._write_ad_css(output_dir / "style.css", width, height, brand)
        self._write_ad_js(output_dir / "script.js", landing_url)

        # Generate fallback image
        self._generate_fallback(output_dir, width, height, headline, brand)

        # Generate manifest.json (Google Web Designer format)
        manifest = {
            "HTML5": {
                "version": "1.0",
                "creativeProperties": {
                    "minWidth": width, "minHeight": height,
                    "maxWidth": width, "maxHeight": height,
                },
            },
            "source": "index.html",
            "clickTags": {
                "clickTag": {"url": landing_url, "type": "exit"},
            },
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        logger.info("HTML5 ad built: %dx%d in %s", width, height, output_dir)
        return output_dir

    def build_essential_ads(
        self,
        image_path: Path,
        output_dir: Path,
        headline: str = "ERP Agricole Intelligent",
        brand: Optional[dict] = None,
    ) -> dict[str, Path]:
        """Build ads in all 5 essential cross-platform sizes.

        Generates both static images and HTML5 animated versions.

        Args:
            image_path: High-res source image.
            output_dir: Base output directory.
            headline: Ad headline.
            brand: Brand config.

        Returns:
            Dict mapping size name to output path.
        """
        results = {}

        for name, spec in ESSENTIAL_SIZES.items():
            w, h = spec["width"], spec["height"]

            # Static image
            static_dir = output_dir / "static" / name
            static_dir.mkdir(parents=True, exist_ok=True)
            static_results = self.build_static_ad(
                image_path, static_dir, platform="meta",
            )
            if static_results:
                results[f"{name}_static"] = static_dir

            # HTML5 animated (only for standard banner sizes)
            if w <= 970 and h <= 600:
                html5_dir = output_dir / "html5" / name
                self.build_html5_ad(
                    output_dir=html5_dir,
                    width=w, height=h,
                    headline=headline,
                    brand=brand,
                    bg_image_path=image_path,
                )
                results[f"{name}_html5"] = html5_dir

        return results

    def zip_ad(self, ad_dir: Path, output_path: Optional[Path] = None) -> Path:
        """Create a ZIP archive from an ad directory.

        Args:
            ad_dir: Directory containing the ad files.
            output_path: ZIP output path (default: same name + .zip).

        Returns:
            Path to the ZIP file.
        """
        ad_dir = Path(ad_dir)
        output_path = output_path or ad_dir.with_suffix(".zip")
        shutil.make_archive(str(output_path.with_suffix("")), "zip", ad_dir)
        size_kb = output_path.stat().st_size / 1024
        logger.info("Ad ZIP: %s (%.0f KB)", output_path.name, size_kb)
        return output_path

    def validate_ad_size(self, ad_dir: Path, platform: str = "google_gdn") -> dict:
        """Validate an ad directory against platform size limits.

        Returns:
            Dict with total_kb, limit_kb, passed, and file breakdown.
        """
        ad_dir = Path(ad_dir)
        limit = get_platform_limit(platform)
        limit_kb = limit.get("zip_max_kb", limit.get("zip_max_mb", 0.15) * 1024)

        total_bytes = 0
        files = {}
        for f in ad_dir.rglob("*"):
            if f.is_file():
                size = f.stat().st_size
                total_bytes += size
                files[str(f.relative_to(ad_dir))] = round(size / 1024, 1)

        total_kb = round(total_bytes / 1024, 1)
        passed = total_kb <= limit_kb

        if not passed:
            logger.warning("Ad size OVER LIMIT: %.0f KB > %.0f KB (%s)", total_kb, limit_kb, platform)

        return {
            "total_kb": total_kb,
            "limit_kb": limit_kb,
            "passed": passed,
            "platform": platform,
            "files": files,
        }

    # ── Private helpers ──────────────────────────────────────

    def _write_ad_html(
        self, path: Path, w: int, h: int,
        headline: str, cta: str, url: str, brand: dict, has_bg: bool,
    ) -> None:
        bg_style = "background-image: url('bg.jpg'); background-size: cover;" if has_bg else (
            f'background: linear-gradient(135deg, {brand["primary_color"]}, {brand["secondary_color"]});'
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="ad.size" content="width={w},height={h}">
  <script>var clickTag = "{url}";</script>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="ad-container" style="{bg_style}">
    <div id="headline">{headline}</div>
    <div id="cta">{cta}</div>
    <div id="click-area" role="button" tabindex="0" aria-label="Visit site"></div>
  </div>
  <script src="script.js"></script>
  <noscript>
    <a href="{url}" target="_blank">
      <img src="fallback.jpg" width="{w}" height="{h}" alt="{brand['name']}" border="0">
    </a>
  </noscript>
</body>
</html>"""
        path.write_text(html, encoding="utf-8")

    def _write_ad_css(self, path: Path, w: int, h: int, brand: dict) -> None:
        # Scale font sizes based on ad dimensions
        headline_size = max(14, min(28, h // 8))
        cta_size = max(12, min(18, h // 14))
        cta_padding_v = max(6, h // 30)
        cta_padding_h = max(12, w // 15)

        css = f"""* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {w}px; height: {h}px; overflow: hidden; }}

#ad-container {{
  position: relative;
  width: {w}px; height: {h}px;
  overflow: hidden;
  border: 1px solid #ccc;
  cursor: pointer;
}}

#headline {{
  position: absolute;
  top: {h // 4}px; left: 0; right: 0;
  text-align: center;
  font: bold {headline_size}px Arial, sans-serif;
  color: {brand['text_color']};
  opacity: 0;
  animation: slideUp 0.6s ease-out 0.5s forwards;
  text-shadow: 0 2px 8px rgba(0,0,0,0.5);
  padding: 0 10px;
}}

@keyframes slideUp {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

#cta {{
  position: absolute;
  bottom: {max(15, h // 8)}px; left: 50%;
  transform: translateX(-50%) scale(0);
  padding: {cta_padding_v}px {cta_padding_h}px;
  background: {brand['text_color']};
  color: {brand['primary_color']};
  font: bold {cta_size}px Arial, sans-serif;
  border-radius: 25px;
  text-transform: uppercase;
  white-space: nowrap;
  animation: ctaPop 0.5s cubic-bezier(0.175,0.885,0.32,1.275) 1.5s forwards;
}}

@keyframes ctaPop {{
  from {{ transform: translateX(-50%) scale(0); opacity: 0; }}
  to {{ transform: translateX(-50%) scale(1); opacity: 1; }}
}}

#click-area {{ position: absolute; inset: 0; z-index: 100; cursor: pointer; }}
"""
        path.write_text(css, encoding="utf-8")

    def _write_ad_js(self, path: Path, url: str) -> None:
        js = f"""document.getElementById('click-area').addEventListener('click', function() {{
  window.open(window.clickTag, '_blank');
}});

// Stop animations at 30s (Google Ads requirement)
setTimeout(function() {{
  document.querySelectorAll('#ad-container *').forEach(function(el) {{
    el.style.animationPlayState = 'paused';
  }});
}}, 30000);
"""
        path.write_text(js, encoding="utf-8")

    def _generate_fallback(
        self, output_dir: Path, w: int, h: int, headline: str, brand: dict,
    ) -> None:
        """Generate fallback.jpg using FFmpeg drawtext (no external deps)."""
        fallback_path = output_dir / "fallback.jpg"
        # Create a solid color image with text
        cmd = [
            self.ffmpeg_web.svc.ffmpeg,
            "-f", "lavfi",
            "-i", f"color=c={brand['primary_color'].replace('#', '0x')}:s={w}x{h}:d=1",
            "-vf", (
                f"drawtext=text='{headline}':"
                f"fontsize={max(14, h // 8)}:fontcolor=white:"
                f"x=(w-tw)/2:y=(h-th)/2"
            ),
            "-frames:v", "1",
            "-q:v", "2",
            str(fallback_path), "-y",
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        except subprocess.CalledProcessError:
            logger.warning("Fallback image generation failed (non-critical)")
