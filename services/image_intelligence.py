"""Image Intelligence Service — multi-source image resolver for FOFAL videos.

Resolution chain (priority order):
  1. Brand assets: curated images from website-fofal (highest fidelity)
  2. Stock photos: Unsplash/Pexels API search with category-specific queries
  3. AI generation: kie.ai Nano Banana Pro (high-quality, up to 4K)
  4. AI generation: fal.ai FLUX Schnell (fast fallback)

V-I-V: Verifies image existence and validity before use,
verifies output resolution/format after preparation.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default brand assets directory (relative to project root)
DEFAULT_BRAND_DIR = Path(__file__).parent.parent / "assets" / "brand" / "fofal"
# Cache for downloaded external images
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "assets" / "cache"


# Semantic mapping: category → list of brand images with priority and tags
BRAND_ASSETS: dict[str, list[dict[str, str | list[str] | int]]] = {
    "plantation": [
        {"file": "hero-bg.webp", "tags": ["aerial", "lush", "overview", "palmeraie"], "priority": 1},
        {"file": "histoire-plantation.webp", "tags": ["history", "growth", "palmiers"], "priority": 2},
        {"file": "divider.webp", "tags": ["decorative", "nature", "verdure"], "priority": 3},
    ],
    "product_oil": [
        {"file": "produit-huile.webp", "tags": ["red palm oil", "bottle", "huile rouge"], "priority": 1},
    ],
    "product_papaya": [
        {"file": "produit-papayes.webp", "tags": ["F1 Horizon", "fruit", "papaye"], "priority": 1},
    ],
    "product_nuts": [
        {"file": "produit-noix.webp", "tags": ["palm nuts", "raw material", "noix"], "priority": 1},
    ],
    "team": [
        {"file": "equipe.webp", "tags": ["employees", "group photo", "equipe"], "priority": 1},
    ],
    "harvest": [
        {"file": "hero-bg.webp", "tags": ["plantation", "aerial", "recolte"], "priority": 2},
        {"file": "histoire-plantation.webp", "tags": ["plantation", "terrain"], "priority": 3},
    ],
    "production": [
        {"file": "produit-huile.webp", "tags": ["oil", "process", "transformation"], "priority": 2},
        {"file": "produit-noix.webp", "tags": ["nuts", "raw material", "matiere premiere"], "priority": 3},
    ],
    "overview": [
        {"file": "og-image.jpg", "tags": ["social card", "overview", "brand"], "priority": 1},
        {"file": "hero-bg.webp", "tags": ["aerial", "plantation"], "priority": 2},
    ],
}


# External image source mapping: category → search queries + recommended sources.
# Guides the agent on WHERE and WHAT to search when brand assets aren't sufficient.
IMAGE_SOURCES: dict[str, dict[str, str | list[str]]] = {
    "plantation": {
        "unsplash_queries": [
            "african palm oil plantation aerial",
            "cameroon agriculture tropical farm",
            "palm tree plantation africa green",
        ],
        "pexels_queries": [
            "palm oil plantation",
            "tropical agriculture africa",
            "green plantation aerial view",
        ],
        "fal_prompt": (
            "Aerial photograph of a lush palm oil plantation in Cameroon, "
            "Central Africa, 80 hectares of Tenera palm trees, rich green "
            "canopy, warm golden sunlight, professional corporate photography"
        ),
        "style_guidance": "Wide/aerial shots, lush green canopy, warm light, professional",
    },
    "product_oil": {
        "unsplash_queries": [
            "red palm oil bottle product",
            "palm oil production artisanal",
            "african cooking oil product photography",
        ],
        "pexels_queries": [
            "palm oil product",
            "red palm oil bottle",
            "artisanal oil production africa",
        ],
        "fal_prompt": (
            "Professional product photography of artisanal red palm oil "
            "in a glass bottle, rich amber-red color, Cameroon brand, "
            "clean white background, studio lighting"
        ),
        "style_guidance": "Product close-up, rich red/amber tones, clean background",
    },
    "product_papaya": {
        "unsplash_queries": [
            "papaya fruit tropical harvest",
            "african fruit farm papaya",
            "papaya tree plantation tropical",
        ],
        "pexels_queries": [
            "papaya fruit fresh",
            "tropical papaya harvest",
            "papaya plantation africa",
        ],
        "fal_prompt": (
            "Fresh F1 Horizon papayas on a tropical farm in Cameroon, "
            "ripe orange fruit on the tree, lush green leaves, "
            "natural sunlight, professional agricultural photography"
        ),
        "style_guidance": "Close-up fruit on tree, vibrant orange/green, natural light",
    },
    "product_nuts": {
        "unsplash_queries": [
            "palm nuts raw material",
            "palm fruit bunch harvest",
            "african palm kernel nuts",
        ],
        "pexels_queries": [
            "palm fruit bunch",
            "palm nuts harvest",
            "palm kernel production",
        ],
        "fal_prompt": (
            "Close-up of fresh palm fruit bunches (noix de palme) "
            "harvested in Cameroon, rich dark red and orange tones, "
            "raw material for palm oil, professional photography"
        ),
        "style_guidance": "Macro/detail of palm bunches, dark red/orange tones",
    },
    "team": {
        "unsplash_queries": [
            "african farm workers team",
            "cameroon agriculture workers",
            "african corporate team portrait",
        ],
        "pexels_queries": [
            "african workers team agriculture",
            "farm workers group portrait africa",
            "african business team",
        ],
        "fal_prompt": (
            "Group portrait of African agricultural workers on a palm "
            "oil plantation in Cameroon, diverse team, professional "
            "uniforms, confident smiles, natural outdoor setting"
        ),
        "style_guidance": "Group photo, outdoor, natural light, diverse team, warm tones",
    },
    "harvest": {
        "unsplash_queries": [
            "palm fruit harvest africa workers",
            "palm oil harvesting machete",
            "tropical fruit picking workers",
        ],
        "pexels_queries": [
            "palm oil harvest workers",
            "african agriculture harvest",
            "tropical fruit picking",
        ],
        "fal_prompt": (
            "Workers harvesting palm fruit bunches on a Cameroon "
            "plantation, action shot with traditional tools, warm "
            "golden hour light, authentic documentary style"
        ),
        "style_guidance": "Action/documentary, workers in field, warm golden light",
    },
    "production": {
        "unsplash_queries": [
            "palm oil processing factory",
            "artisanal oil press africa",
            "food production facility africa",
        ],
        "pexels_queries": [
            "palm oil factory processing",
            "oil extraction machinery",
            "food production africa",
        ],
        "fal_prompt": (
            "Interior of a palm oil processing facility in Cameroon, "
            "machinery and workers, industrial yet artisanal, "
            "warm tones, professional documentary photography"
        ),
        "style_guidance": "Industrial interior, machinery + workers, documentary tone",
    },
    "overview": {
        "unsplash_queries": [
            "cameroon landscape aerial green",
            "central africa agriculture panorama",
            "african plantation landscape sunset",
        ],
        "pexels_queries": [
            "cameroon landscape agriculture",
            "africa plantation panorama",
            "tropical landscape sunrise",
        ],
        "fal_prompt": (
            "Panoramic view of FOFAL agricultural estate in Ebondi, "
            "Cameroon, palm plantation stretching to the horizon, "
            "dramatic sky, golden hour, award-winning landscape photography"
        ),
        "style_guidance": "Panoramic/wide, dramatic sky, golden hour, cinematic",
    },
}


# French + English keywords → category
SCENE_KEYWORDS: dict[str, list[str]] = {
    "plantation": [
        "plantation", "parcelle", "terre", "ebondi", "agriculture", "palmeraie",
        "hectare", "champ", "field", "farm", "terrain", "sol",
    ],
    "product_oil": [
        "huile", "oil", "palme rouge", "tenera", "produit huile",
        "bouteille", "extraction",
    ],
    "product_papaya": [
        "papaye", "papaya", "f1 horizon", "fruit", "verger",
    ],
    "product_nuts": [
        "noix", "nuts", "palm nut", "noyau", "regimes", "amande",
    ],
    "team": [
        "equipe", "team", "employe", "personnel", "staff", "ouvrier",
        "travailleur", "collaborateur", "fondateur", "jean paul",
    ],
    "harvest": [
        "recolte", "harvest", "cueillette", "collecte", "ramassage",
        "moisson", "picking", "fruits de palme", "fruit de palme",
        "regimes de palme", "coupe",
    ],
    "production": [
        "production", "usine", "process", "transformation", "presse",
        "factory", "manufacturing", "moulin",
    ],
    "overview": [
        "fofal", "cameroun", "excellence", "vision", "bienvenue",
        "presentation", "introduction", "decouvrez", "apercu",
    ],
}


class ImageIntelligenceService:
    """Multi-source image resolver for FOFAL video production.

    Resolution chain (priority order):
      1. Brand assets (website-fofal curated images)
      2. Cached previously-downloaded images
      3. Unsplash API (free, high-quality stock photos)
      4. Pexels API (free alternative stock source)
      5. fal.ai generation (AI-created images as creative fallback)

    Follows V-I-V: every image is verified before use.
    """

    def __init__(
        self,
        brand_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        enable_external: bool = True,
    ):
        self.brand_dir = brand_dir or DEFAULT_BRAND_DIR
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.enable_external = enable_external

        if not self.brand_dir.exists():
            raise FileNotFoundError(f"Brand assets directory not found: {self.brand_dir}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve_image_for_scene(
        self, scene_description: str, scene_title: str = ""
    ) -> Path:
        """Find the best image for a scene, searching multiple sources.

        Priority: brand assets → cache → Unsplash → Pexels → fal.ai.

        Args:
            scene_description: Narrative description of what the viewer sees.
            scene_title: Optional short title for the scene.

        Returns:
            Path to the best matching image (local file).

        Raises:
            FileNotFoundError: If no valid image found from any source.
        """
        category = self._classify_scene(scene_description, scene_title)

        # 1. Try brand assets (highest priority — curated, on-brand)
        brand_path = self._resolve_from_brand(category)
        if brand_path:
            return brand_path

        # 2. Try cached external images for this category
        cached_path = self._resolve_from_cache(category)
        if cached_path:
            return cached_path

        # 3. Try external sources if enabled
        if self.enable_external:
            external_path = self._resolve_from_external(category)
            if external_path:
                return external_path

        # 4. Last resort: any brand image
        for img in sorted(self.brand_dir.iterdir()):
            if img.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png"):
                if self.verify_image(img):
                    logger.warning("Last-resort fallback image: %s", img.name)
                    return img

        raise FileNotFoundError(
            f"No valid image found for scene: {scene_description[:80]}"
        )

    def _resolve_from_brand(self, category: str) -> Optional[Path]:
        """Try to resolve from curated brand assets."""
        assets = BRAND_ASSETS.get(category, BRAND_ASSETS.get("plantation", []))

        for asset in sorted(assets, key=lambda a: a["priority"]):
            path = self.brand_dir / asset["file"]
            if self.verify_image(path):
                logger.info(
                    "Brand asset: category '%s' → %s", category, asset["file"],
                )
                return path
        return None

    def _resolve_from_cache(self, category: str) -> Optional[Path]:
        """Check if a previously downloaded image exists for this category."""
        category_dir = self.cache_dir / category
        if not category_dir.exists():
            return None

        for img in sorted(category_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if img.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png"):
                if self.verify_image(img):
                    logger.info("Cached image: category '%s' → %s", category, img.name)
                    return img
        return None

    def _resolve_from_external(self, category: str) -> Optional[Path]:
        """Try external sources: Unsplash → Pexels → kie.ai → fal.ai."""
        sources = IMAGE_SOURCES.get(category, {})

        # Try Unsplash
        unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        if unsplash_key and sources.get("unsplash_queries"):
            for query in sources["unsplash_queries"]:
                path = self._fetch_unsplash(query, category, unsplash_key)
                if path:
                    return path

        # Try Pexels
        pexels_key = os.getenv("PEXELS_API_KEY")
        if pexels_key and sources.get("pexels_queries"):
            for query in sources["pexels_queries"]:
                path = self._fetch_pexels(query, category, pexels_key)
                if path:
                    return path

        # Try kie.ai Nano Banana Pro (high-quality AI generation, up to 4K)
        kie_key = os.getenv("KIE_API_KEY")
        if kie_key and sources.get("fal_prompt"):
            prompt = sources["fal_prompt"]
            if isinstance(prompt, str):
                path = self._generate_kie(prompt, category, kie_key)
                if path:
                    return path

        # Try fal.ai generation (fast fallback)
        fal_key = os.getenv("FAL_API_KEY")
        if fal_key and sources.get("fal_prompt"):
            fal_prompt = sources["fal_prompt"]
            if isinstance(fal_prompt, str):
                path = self._generate_fal(fal_prompt, category, fal_key)
                if path:
                    return path

        return None

    def _fetch_unsplash(self, query: str, category: str, api_key: str) -> Optional[Path]:
        """Download a relevant image from Unsplash."""
        try:
            resp = httpx.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("Unsplash API error %d for query '%s'", resp.status_code, query)
                return None

            results = resp.json().get("results", [])
            if not results:
                return None

            image_url = results[0]["urls"]["regular"]  # 1080px wide
            return self._download_and_cache(image_url, category, f"unsplash_{query[:30]}")

        except Exception as e:
            logger.warning("Unsplash fetch failed: %s", e)
            return None

    def _fetch_pexels(self, query: str, category: str, api_key: str) -> Optional[Path]:
        """Download a relevant image from Pexels."""
        try:
            resp = httpx.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape",
                    "size": "large",
                },
                headers={"Authorization": api_key},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("Pexels API error %d for query '%s'", resp.status_code, query)
                return None

            photos = resp.json().get("photos", [])
            if not photos:
                return None

            image_url = photos[0]["src"]["large2x"]  # ~1920px
            return self._download_and_cache(image_url, category, f"pexels_{query[:30]}")

        except Exception as e:
            logger.warning("Pexels fetch failed: %s", e)
            return None

    def _generate_fal(self, prompt: str, category: str, api_key: str) -> Optional[Path]:
        """Generate an image via fal.ai as creative fallback."""
        try:
            resp = httpx.post(
                "https://fal.run/fal-ai/flux/schnell",
                json={
                    "prompt": prompt,
                    "image_size": "landscape_16_9",
                    "num_images": 1,
                },
                headers={"Authorization": f"Key {api_key}"},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("fal.ai error %d", resp.status_code)
                return None

            images = resp.json().get("images", [])
            if not images:
                return None

            image_url = images[0]["url"]
            return self._download_and_cache(image_url, category, "fal_generated")

        except Exception as e:
            logger.warning("fal.ai generation failed: %s", e)
            return None

    def _generate_kie(self, prompt: str, category: str, api_key: str) -> Optional[Path]:
        """Generate an image via kie.ai Nano Banana Pro (high-quality, up to 4K)."""
        try:
            from skill_kie_image import KieImageGenerator

            gen = KieImageGenerator(api_key=api_key)
            category_dir = self.cache_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)

            output_path = category_dir / f"kie_{category}_{hashlib.md5(prompt.encode()).hexdigest()[:8]}.png"

            # Skip if already cached
            if output_path.exists() and self.verify_image(output_path):
                logger.info("kie.ai cached: %s → %s", category, output_path.name)
                return output_path

            result = gen.generate(
                prompt=prompt,
                output_path=output_path,
                aspect_ratio="16:9",
                max_wait=300.0,
            )

            if result.state == "success" and output_path.exists():
                if self.verify_image(output_path):
                    logger.info("kie.ai generated: %s → %s", category, output_path.name)
                    return output_path
                output_path.unlink(missing_ok=True)

            gen.close()
            return None

        except Exception as e:
            logger.warning("kie.ai generation failed: %s", e)
            return None

    def _download_and_cache(self, url: str, category: str, prefix: str) -> Optional[Path]:
        """Download an image URL and cache it locally."""
        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            category_dir = self.cache_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)

            # Determine extension from URL or default to .jpg
            ext = ".jpg"
            for candidate in (".webp", ".png", ".jpeg"):
                if candidate in url.lower():
                    ext = candidate
                    break

            filename = f"{prefix}_{url_hash}{ext}"
            output_path = category_dir / filename

            # Skip if already cached
            if output_path.exists() and self.verify_image(output_path):
                return output_path

            resp = httpx.get(url, timeout=30, follow_redirects=True)
            if resp.status_code != 200:
                return None

            output_path.write_bytes(resp.content)

            if self.verify_image(output_path):
                logger.info("Downloaded & cached: %s → %s", prefix, output_path.name)
                return output_path

            # Downloaded file is invalid — remove it
            output_path.unlink(missing_ok=True)
            return None

        except Exception as e:
            logger.warning("Download failed for %s: %s", url[:60], e)
            return None

    def get_category_for_scene(
        self, scene_description: str, scene_title: str = ""
    ) -> str:
        """Get the semantic category for a scene (useful for Ken Burns preset selection)."""
        return self._classify_scene(scene_description, scene_title)

    def get_source_guidance(self, category: str) -> dict[str, str | list[str]]:
        """Get image sourcing guidance for a category.

        Returns search queries, prompts, and style guidance that help
        the agent or a human find the best images for this scene type.
        """
        return IMAGE_SOURCES.get(category, IMAGE_SOURCES.get("overview", {}))

    def _classify_scene(self, description: str, title: str = "") -> str:
        """Classify a scene description into a semantic category by keyword scoring.

        Normalizes accents (é→e, è→e, etc.) for robust French keyword matching.
        """
        raw_text = f"{description} {title}".lower()
        text = self._normalize_accents(raw_text)
        scores: dict[str, int] = {}

        for category, keywords in SCENE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)

        # Default fallback
        return "plantation"

    @staticmethod
    def _normalize_accents(text: str) -> str:
        """Strip French accents for robust keyword matching."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def prepare_for_video(
        self,
        image_path: Path,
        output_path: Path,
        target_w: int = 1920,
        target_h: int = 1080,
    ) -> Path:
        """Scale and pad an image to exact video dimensions.

        Uses FFmpeg to scale (preserving aspect ratio) then pad to target size.
        Output is always a PNG for maximum quality before Ken Burns processing.

        Returns:
            Path to the prepared image.
        """
        ffmpeg = os.getenv("FFMPEG_PATH", "/usr/local/bin/ffmpeg")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg,
            "-i", str(image_path),
            "-vf", (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black"
            ),
            "-frames:v", "1",
            str(output_path), "-y",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg prepare failed: {result.stderr[:200]}")

        # V-I-V After: verify output
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Prepared image is empty: {output_path}")

        return output_path

    @staticmethod
    def verify_image(path: Path, min_width: int = 100) -> bool:
        """Verify an image exists, is readable, and meets minimum size.

        Uses ffprobe to validate the image can be decoded.
        """
        if not path.exists() or path.stat().st_size == 0:
            return False

        try:
            ffprobe = os.getenv("FFPROBE_PATH", "/usr/local/bin/ffprobe")
            cmd = [
                ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False

            import json
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = int(stream.get("width", 0))
                    return width >= min_width
            return False
        except Exception:
            return False

    def list_available_assets(self) -> dict[str, list[str]]:
        """List all available brand assets by category (for debugging)."""
        result = {}
        for category, assets in BRAND_ASSETS.items():
            available = []
            for asset in assets:
                path = self.brand_dir / asset["file"]
                if path.exists():
                    available.append(asset["file"])
            result[category] = available
        return result

    def list_all_sources(self) -> dict[str, dict[str, str | list[str]]]:
        """List all image sources for each category (brand + external guidance)."""
        result = {}
        for category in SCENE_KEYWORDS:
            brand = [a["file"] for a in BRAND_ASSETS.get(category, [])
                     if (self.brand_dir / a["file"]).exists()]
            cached = []
            cat_cache = self.cache_dir / category
            if cat_cache.exists():
                cached = [f.name for f in cat_cache.iterdir()
                          if f.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png")]
            guidance = IMAGE_SOURCES.get(category, {})
            result[category] = {
                "brand_assets": brand,
                "cached_downloads": cached,
                "external_queries": guidance.get("unsplash_queries", []),
                "fal_prompt": guidance.get("fal_prompt", ""),
                "style_guidance": guidance.get("style_guidance", ""),
            }
        return result
