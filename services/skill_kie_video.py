"""KIE.ai Video Generation — Kling models for AI video from text/image.

Models available:
  - kling/v2-1-standard:            Kling 2.1 Standard ($0.125/5s)
  - kling/v2-1-pro:                 Kling 2.1 Pro ($0.25/5s)
  - kling/v2-1-master-image-to-video: Kling 2.1 Master ($0.80/5s)
  - kling-2.6/text-to-video:        Kling 2.6 Text-to-Video
  - kling-2.6/image-to-video:       Kling 2.6 Image-to-Video
  - kling-2.6/motion-control:       Kling 2.6 Motion Control
  - kling-3.0/video:                Kling 3.0 (RECOMMENDED)

Kling 3.0 Parameters:
  - prompt (max 2500 chars, supports @element_name)
  - image_urls: start/end frames (JPG/PNG, min 300px, max 10MB)
  - sound: boolean (native audio in 5+ languages)
  - duration: "3"-"15" seconds
  - aspect_ratio: 16:9, 9:16, 1:1
  - mode: std or pro
  - multi_shots: boolean
  - multi_prompt: [{prompt, duration}] per shot
  - kling_elements: element references (2-4 images or 1 video)

V-I-V: Validates prompt length, image URLs, downloads result video.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from kie_client import KieClient, KieTaskResult

logger = logging.getLogger(__name__)

# Model registry with costs and capabilities
MODELS = {
    "kling/v2-1-standard": {"cost_5s": 0.125, "max_duration": 10},
    "kling/v2-1-pro": {"cost_5s": 0.25, "max_duration": 10},
    "kling/v2-1-master-image-to-video": {"cost_5s": 0.80, "max_duration": 10},
    "kling-2.6/text-to-video": {"cost_5s": None, "max_duration": 10},
    "kling-2.6/image-to-video": {"cost_5s": None, "max_duration": 10},
    "kling-2.6/motion-control": {"cost_5s": None, "max_duration": 10},
    "kling-3.0/video": {"cost_5s": None, "max_duration": 15},
}


class KieVideoGenerator:
    """Generate videos via kie.ai Kling models.

    Supports text-to-video and image-to-video workflows.
    Kling 3.0 is the recommended model for quality and features.

    Usage:
        gen = KieVideoGenerator()

        # Text-to-video
        result = gen.generate(
            prompt="A dragon flying over a medieval castle",
            output_path=Path("output/dragon.mp4"),
            duration="10",
        )

        # Image-to-video (start frame)
        result = gen.generate(
            prompt="Camera slowly zooming into the plantation",
            output_path=Path("output/plantation.mp4"),
            image_urls=["https://example.com/start_frame.png"],
            duration="10",
        )
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = KieClient(api_key=api_key)

    def generate(
        self,
        prompt: str,
        output_path: Path,
        model: str = "kling-3.0/video",
        duration: str = "10",
        aspect_ratio: str = "16:9",
        mode: str = "pro",
        sound: bool = True,
        image_urls: Optional[list[str]] = None,
        multi_shots: bool = False,
        multi_prompt: Optional[list[dict]] = None,
        kling_elements: Optional[list[dict]] = None,
        max_wait: float = 600.0,
    ) -> KieTaskResult:
        """Generate a video from text prompt and optional start frame.

        Args:
            prompt: Text description (max 2500 chars for Kling 3.0).
            output_path: Local path to save the generated video.
            model: Kling model variant.
            duration: Video duration in seconds (3-15 for Kling 3.0).
            aspect_ratio: Output aspect ratio (16:9, 9:16, 1:1).
            mode: Quality mode (std or pro).
            sound: Enable native audio generation.
            image_urls: Optional start/end frame URLs for image-to-video.
            multi_shots: Enable multi-shot generation.
            multi_prompt: Per-shot prompt and duration list.
            kling_elements: Element references for character consistency.
            max_wait: Maximum wait for generation (videos take longer).

        Returns:
            KieTaskResult with local video file path.
        """
        # V-I-V Verify: validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("Prompt must not be empty")
        if len(prompt) > 2500:
            logger.warning("Prompt truncated from %d to 2500 chars", len(prompt))
            prompt = prompt[:2500]
        if model not in MODELS:
            raise ValueError(f"Unknown model '{model}'. Available: {list(MODELS.keys())}")

        output_path = Path(output_path)

        # Build input params
        input_params: dict = {
            "prompt": prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
            "mode": mode,
            "sound": sound,
        }

        # Kling 3.0 requires multi_shots to be explicitly set
        input_params["multi_shots"] = multi_shots

        if image_urls:
            input_params["image_urls"] = image_urls
        if multi_prompt:
            input_params["multi_prompt"] = multi_prompt
        if kling_elements:
            input_params["kling_elements"] = kling_elements

        # Video generation takes longer than images
        result = self.client.generate_and_download(
            model=model,
            input_params=input_params,
            output_path=output_path,
            poll_interval=8.0,  # Videos take longer
            max_wait=max_wait,
        )

        # V-I-V Verify: validate output
        if result.state == "success":
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                if size_mb < 0.01:
                    logger.warning("Generated video is suspiciously small: %.2f MB", size_mb)
                    result.error_message = f"Video too small ({size_mb:.2f} MB)"
                    result.state = "fail"
                else:
                    logger.info(
                        "Video generated: %s (%.1f MB, %ss, %s, mode=%s)",
                        output_path.name, size_mb, duration, aspect_ratio, mode,
                    )
            else:
                result.error_message = "Download succeeded but file not found"
                result.state = "fail"

        return result

    def generate_from_image(
        self,
        prompt: str,
        image_path_or_url: str,
        output_path: Path,
        duration: str = "10",
        aspect_ratio: str = "16:9",
        model: str = "kling-3.0/video",
    ) -> KieTaskResult:
        """Generate video from a start frame image.

        For local images, they must first be uploaded to a public URL.
        Pass direct URLs for images already hosted.

        Args:
            prompt: Motion/scene description.
            image_path_or_url: URL to the start frame image.
            output_path: Where to save the video.
            duration: Video duration.
            aspect_ratio: Output aspect ratio.
            model: Kling model to use.

        Returns:
            KieTaskResult with local video path.
        """
        return self.generate(
            prompt=prompt,
            output_path=output_path,
            model=model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            image_urls=[image_path_or_url],
        )

    def generate_ad_video(
        self,
        prompt: str,
        output_path: Path,
        duration: str = "5",
        aspect_ratio: str = "16:9",
        sound: bool = False,
    ) -> KieTaskResult:
        """Generate a short video for ads (5-15s, no sound by default).

        Optimized for ad formats: short duration, clean visuals.

        Args:
            prompt: Ad scene description.
            output_path: Where to save the video.
            duration: Ad duration (5, 6, 10, 15).
            aspect_ratio: Target platform ratio.
            sound: Whether to include audio.

        Returns:
            KieTaskResult.
        """
        return self.generate(
            prompt=prompt,
            output_path=output_path,
            duration=duration,
            aspect_ratio=aspect_ratio,
            mode="pro",
            sound=sound,
        )

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
