"""KIE.ai Image Generation — Nano Banana models for high-quality AI images.

Models available:
  - nano-banana:     Standard quality (~$0.02/image)
  - nano-banana-2:   Standard + Google Search grounding (~$0.02)
  - nano-banana-pro: Up to 4K resolution (~$0.03) — RECOMMENDED
  - nano-banana-edit: Image editing via text (~$0.02)

Parameters:
  - prompt (required): Text description
  - aspect_ratio: 1:1, 16:9, 9:16, 3:2, 2:3
  - resolution: 1K, 2K, 4K (nano-banana-pro only)
  - output_format: png, jpeg
  - image_input: list of URLs for image-to-image

V-I-V: Verifies prompt, validates downloaded image, checks resolution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from kie_client import KieClient, KieTaskResult

logger = logging.getLogger(__name__)

# Aspect ratio → recommended use case
ASPECT_RATIOS = {
    "1:1": "Square (Instagram feed, LinkedIn carousel, ads 1080x1080)",
    "16:9": "Landscape (YouTube thumbnail, website hero, video frame)",
    "9:16": "Portrait (Stories, Reels, TikTok)",
    "3:2": "Photo standard (landscape photography)",
    "2:3": "Photo portrait (vertical photography)",
    "4:5": "Meta Feed optimal (more visible surface)",
}

# Model capabilities
MODELS = {
    "nano-banana": {"resolution": ["1K"], "cost": 0.02, "features": ["text-to-image"]},
    "nano-banana-2": {"resolution": ["1K"], "cost": 0.02, "features": ["text-to-image", "grounding"]},
    "nano-banana-pro": {"resolution": ["1K", "2K", "4K"], "cost": 0.03, "features": ["text-to-image", "image-to-image"]},
    "nano-banana-edit": {"resolution": ["1K"], "cost": 0.02, "features": ["image-editing"]},
}


class KieImageGenerator:
    """Generate images via kie.ai Nano Banana models.

    Wraps KieClient with image-specific validation and defaults.

    Usage:
        gen = KieImageGenerator()
        result = gen.generate(
            prompt="Aerial view of a palm oil plantation in Cameroon",
            output_path=Path("output/hero.png"),
            aspect_ratio="16:9",
            resolution="2K",
        )
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = KieClient(api_key=api_key)

    def generate(
        self,
        prompt: str,
        output_path: Path,
        model: str = "nano-banana-pro",
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        output_format: str = "png",
        image_input: Optional[list[str]] = None,
        max_wait: float = 300.0,
    ) -> KieTaskResult:
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the desired image.
            output_path: Local path to save the generated image.
            model: Nano Banana model variant.
            aspect_ratio: Output aspect ratio.
            resolution: Output resolution (1K/2K/4K, pro model only).
            output_format: png or jpeg.
            image_input: Optional list of image URLs for image-to-image.
            max_wait: Maximum wait for generation in seconds.

        Returns:
            KieTaskResult with local file path.
        """
        # V-I-V Verify: validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("Prompt must not be empty")
        if model not in MODELS:
            raise ValueError(f"Unknown model '{model}'. Available: {list(MODELS.keys())}")
        if resolution != "1K" and model != "nano-banana-pro":
            logger.warning(
                "Resolution %s only supported by nano-banana-pro, falling back to 1K",
                resolution,
            )
            resolution = "1K"

        output_path = Path(output_path)

        # Build input params
        input_params: dict = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": output_format,
        }
        if model == "nano-banana-pro":
            input_params["resolution"] = resolution
        if image_input:
            input_params["image_input"] = image_input

        # Generate and download
        result = self.client.generate_and_download(
            model=model,
            input_params=input_params,
            output_path=output_path,
            max_wait=max_wait,
        )

        # V-I-V Verify: validate output
        if result.state == "success":
            if output_path.exists():
                size_kb = output_path.stat().st_size / 1024
                if size_kb < 1:
                    logger.warning("Generated image is suspiciously small: %.1f KB", size_kb)
                    result.error_message = f"Image too small ({size_kb:.1f} KB)"
                    result.state = "fail"
                else:
                    logger.info(
                        "Image generated: %s (%.0f KB, %s, %s)",
                        output_path.name, size_kb, aspect_ratio, resolution,
                    )
            else:
                result.error_message = "Download succeeded but file not found"
                result.state = "fail"

        return result

    def generate_for_ad(
        self,
        prompt: str,
        output_dir: Path,
        platform: str = "meta",
        model: str = "nano-banana-pro",
    ) -> dict[str, KieTaskResult]:
        """Generate images in all required sizes for an ad platform.

        Args:
            prompt: Base prompt for the image.
            output_dir: Directory to save generated images.
            platform: Target platform (meta, google, linkedin).
            model: Nano Banana model to use.

        Returns:
            Dict mapping size name to KieTaskResult.
        """
        from ad_specs import get_platform_image_sizes

        sizes = get_platform_image_sizes(platform)
        results = {}

        for size_name, spec in sizes.items():
            aspect = spec.get("aspect_ratio", "1:1")
            output_path = output_dir / f"{platform}_{size_name}.{spec.get('format', 'png')}"

            logger.info("Generating ad image: %s %s (%s)", platform, size_name, aspect)
            result = self.generate(
                prompt=prompt,
                output_path=output_path,
                model=model,
                aspect_ratio=aspect,
                resolution="2K",
            )
            results[size_name] = result

        return results

    def generate_start_frame(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str = "16:9",
    ) -> KieTaskResult:
        """Generate a start frame image for video generation (Kling 3.0).

        The image will be used as image_urls input for video generation.
        Uses nano-banana-pro at 2K for best quality.

        Args:
            prompt: Scene description for the start frame.
            output_path: Where to save the image.
            aspect_ratio: Aspect ratio matching target video.

        Returns:
            KieTaskResult with local file path.
        """
        return self.generate(
            prompt=f"Cinematic still frame, photorealistic: {prompt}",
            output_path=output_path,
            model="nano-banana-pro",
            aspect_ratio=aspect_ratio,
            resolution="2K",
            output_format="png",
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
