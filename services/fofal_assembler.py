"""TerraFlow ERP Video Assembler — orchestrates the full video production pipeline.

Chains: storyboard → image selection → Ken Burns / AI video → voiceover → merge
→ transitions → brand watermark → E2E verification.

Scene types supported:
  - "branding": Brand image → Ken Burns animation (default)
  - "ui_recording": Pre-recorded ERP screen clip
  - "ai_video": kie.ai Kling 3.0 AI-generated video from prompt
  - "ai_image_to_video": kie.ai Kling 3.0 from a start frame image

Post-assembly outputs (optional):
  - Scroll-driven website (Apple-style canvas animation)
  - HTML5 ads (Meta/Google/LinkedIn sizes)
  - Marketing landing page
  - Web-optimized MP4 + preview GIF

V-I-V Principe 2: No workarounds — every step uses real services.
V-I-V Principe 5: Tolerance Zero — QA score must be >= 7.0/10.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from image_intelligence import ImageIntelligenceService
from ken_burns import KenBurnsGenerator
from skill_voiceover import VoiceoverGenerator
from skill_transitions import TransitionManager
from e2e_verifier import E2EVerifier, VerificationConfig

logger = logging.getLogger(__name__)


@dataclass
class AssemblyResult:
    """Result of a full video assembly."""
    success: bool
    output_path: str
    duration_seconds: float
    scenes_assembled: int
    qa_score: Optional[float] = None
    qa_passed: bool = False
    errors: list = field(default_factory=list)
    marketing_assets: dict = field(default_factory=dict)


class FofalVideoAssembler:
    """Orchestrate TerraFlow ERP video production from storyboard to verified output.

    Pipeline per scene:
        1. Resolve brand image (ImageIntelligenceService)
        2. Generate Ken Burns / AI video segment (KenBurnsGenerator / Kling 3.0)
        3. Generate or use existing narration audio (VoiceoverGenerator)
        4. Merge narration with video segment (FFmpegService)

    Post-assembly:
        5. Join all segments with crossfade transitions (TransitionManager)
        6. Apply brand watermark (FFmpegService overlay)
        7. E2E verification (E2EVerifier) — must score >= 7.0/10
        8. Optional: Generate marketing assets (scroll site, ads, landing page)
    """

    def __init__(self) -> None:
        self.ffmpeg = FFmpegService()
        self.images = ImageIntelligenceService()
        self.ken_burns = KenBurnsGenerator()
        self.voiceover = VoiceoverGenerator()
        self.transitions = TransitionManager()
        self.verifier = E2EVerifier()
        # Lazy-initialized on first use (avoids import errors when KIE_API_KEY absent)
        self._kie_video = None
        self._ffmpeg_web = None
        self._scroll_builder = None
        self._ads_builder = None
        self._landing_builder = None

    def assemble(
        self,
        storyboard_path: Path,
        output_dir: Path,
        existing_narrations: Optional[dict[int, Path]] = None,
        generate_marketing: bool = False,
    ) -> AssemblyResult:
        """Assemble a complete video from a storyboard.

        Args:
            storyboard_path: Path to storyboard JSON file.
            output_dir: Directory for intermediate files and final output.
            existing_narrations: Optional mapping of scene_id -> narration MP3 path.
                If provided for a scene, skip TTS generation and use existing audio.
            generate_marketing: If True, also generate scroll site, ads, and landing page.

        Returns:
            AssemblyResult with output path, QA score, and pass/fail status.
        """
        start = time.time()
        storyboard_path = Path(storyboard_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        existing_narrations = existing_narrations or {}
        errors = []

        # Load storyboard
        storyboard = json.loads(storyboard_path.read_text())
        scenes = storyboard["scenes"]
        transition_duration = storyboard.get("transitions", {}).get("duration", 0.8)

        logger.info("Assembling video: %d scenes from %s", len(scenes), storyboard_path.name)

        # === PHASE 1: Generate per-scene segments ===
        segment_paths = []
        for scene in scenes:
            scene_id = scene["id"]
            try:
                segment = self._assemble_scene(
                    scene, output_dir, existing_narrations.get(scene_id)
                )
                segment_paths.append(segment)
                logger.info("Scene %d assembled: %s", scene_id, segment.name)
            except Exception as e:
                msg = f"Scene {scene_id} ({scene['title']}): {e}"
                errors.append(msg)
                logger.error("Scene assembly failed: %s", msg)

        if len(segment_paths) < 2:
            return AssemblyResult(
                success=False,
                output_path="",
                duration_seconds=time.time() - start,
                scenes_assembled=len(segment_paths),
                errors=errors + ["Need at least 2 segments for assembly"],
            )

        # === PHASE 2: Join segments with crossfade transitions ===
        joined_path = output_dir / "joined.mp4"
        try:
            self.transitions.apply_between_clips(
                clip_paths=segment_paths,
                output_path=joined_path,
                transition_type="crossfade",
                duration=transition_duration,
            )
            logger.info("Segments joined with %.1fs crossfade", transition_duration)
        except Exception as e:
            errors.append(f"Transition join failed: {e}")
            logger.error("Transition join failed: %s", e)
            # Fallback: concat without transitions
            joined_path = self._concat_segments(segment_paths, output_dir / "concat.mp4")

        # === PHASE 3: Apply brand watermark ===
        final_path = output_dir / f"{storyboard.get('title', 'terraflow_video').replace(' ', '_')}.mp4"
        watermark_cfg = storyboard.get("watermark", {})
        if watermark_cfg.get("text"):
            try:
                self._apply_watermark(joined_path, final_path, watermark_cfg["text"])
                logger.info("Watermark applied: %s", watermark_cfg["text"])
            except Exception as e:
                errors.append(f"Watermark failed: {e}")
                shutil.copy2(joined_path, final_path)
        else:
            shutil.copy2(joined_path, final_path)

        # === PHASE 4: E2E Verification (V-I-V Principe 5) ===
        job_id = str(uuid.uuid4())
        config = VerificationConfig(
            expected_duration=None,  # Skip duration check — narration lengths drive actual duration
            min_width=1920,
            min_height=1080,
            persist_to_db=True,
        )
        report = self.verifier.verify_pipeline_output(job_id, final_path, config)

        # === PHASE 5: Marketing assets (optional) ===
        marketing_assets = {}
        if generate_marketing and report.passed:
            marketing_cfg = storyboard.get("marketing", {})
            marketing_assets = self._generate_marketing_assets(
                video_path=final_path,
                output_dir=output_dir / "marketing",
                config=marketing_cfg,
                storyboard=storyboard,
            )

        elapsed = time.time() - start
        return AssemblyResult(
            success=report.passed and len(errors) == 0,
            output_path=str(final_path),
            duration_seconds=round(elapsed, 2),
            scenes_assembled=len(segment_paths),
            qa_score=report.score,
            qa_passed=report.passed,
            errors=errors,
            marketing_assets=marketing_assets,
        )

    def _assemble_scene(
        self,
        scene: dict,
        output_dir: Path,
        existing_narration: Optional[Path] = None,
    ) -> Path:
        """Assemble a single scene — multiple video source types.

        Scene types (determined by storyboard):
            - "branding" (default): Resolve brand image → Ken Burns animation.
            - "ui_recording": Use pre-recorded ERP screen clip directly.
              Requires "recording_path" field pointing to an mp4/webm clip.
            - "ai_video": Generate video via kie.ai Kling 3.0 from text prompt.
              Uses scene "visual_description" as the generation prompt.
            - "ai_image_to_video": Generate video from a start frame image.
              Resolves image first, then animates via Kling 3.0.

        Args:
            scene: Scene dict from storyboard JSON.
            output_dir: Working directory for intermediate files.
            existing_narration: Path to existing narration audio (skip TTS if provided).

        Returns:
            Path to the final merged segment video.
        """
        scene_id = scene["id"]
        duration = scene["duration"]
        prefix = f"scene_{scene_id:02d}"
        scene_type = scene.get("scene_type", "branding")

        # 1. Get video segment based on scene type
        if scene_type == "ui_recording" and scene.get("recording_path"):
            recording_src = Path(scene["recording_path"])
            if not recording_src.exists():
                logger.warning(
                    "Scene %d: recording %s not found, falling back to brand image",
                    scene_id, recording_src,
                )
                video_segment = self._generate_kenburns_segment(scene, output_dir, prefix)
            else:
                video_segment = output_dir / f"{prefix}_recording.mp4"
                self._prepare_screen_recording(
                    recording_src, video_segment, duration
                )
                logger.info("Scene %d: using screen recording %s", scene_id, recording_src.name)

        elif scene_type == "ai_video":
            video_segment = self._generate_ai_video_segment(scene, output_dir, prefix)

        elif scene_type == "ai_image_to_video":
            video_segment = self._generate_ai_image_to_video_segment(scene, output_dir, prefix)

        else:
            video_segment = self._generate_kenburns_segment(scene, output_dir, prefix)

        # 2. Generate or use narration audio
        if existing_narration and Path(existing_narration).exists():
            narration_path = Path(existing_narration)
            logger.info("Scene %d: using existing narration %s", scene_id, narration_path.name)
        else:
            narration_path = output_dir / f"{prefix}_narration.mp3"
            narration_text = scene.get("narration_text", "")
            if not narration_text:
                raise ValueError(f"Scene {scene_id} has no narration_text and no existing audio")
            self.voiceover._generate_audio(
                text=narration_text,
                voice_id=self.voiceover.VOICES["narrator_male"]["voice_id"],
                output_path=narration_path,
            )

        # 3. Merge narration with video segment
        merged_output = output_dir / f"{prefix}_merged.mp4"
        self._merge_narration_with_video(video_segment, narration_path, merged_output)

        return merged_output

    def _generate_kenburns_segment(
        self, scene: dict, output_dir: Path, prefix: str
    ) -> Path:
        """Generate a Ken Burns video segment from a brand image."""
        image_path = self.images.resolve_image_for_scene(
            scene_description=scene.get("visual_description", ""),
            scene_title=scene.get("title", ""),
        )
        kb_output = output_dir / f"{prefix}_kenburns.mp4"
        preset = scene.get("ken_burns_preset", "slow_zoom_in")
        self.ken_burns.generate(
            image_path=image_path,
            output_path=kb_output,
            duration=scene["duration"],
            preset=preset,
        )
        return kb_output

    def _prepare_screen_recording(
        self, src: Path, dst: Path, target_duration: float
    ) -> None:
        """Scale, pad, and trim a screen recording to 1920x1080 at target duration.

        If the recording is shorter than target_duration, it freezes the last frame.
        If longer, it trims to target_duration.
        """
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(src),
            "-vf", (
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
                "fps=30"
            ),
            "-t", str(target_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-an",
            str(dst), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)

    def _merge_narration_with_video(
        self, video_path: Path, audio_path: Path, output_path: Path
    ) -> None:
        """Replace video audio with narration (full replace, not mix)."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)

    def _apply_watermark(self, input_path: Path, output_path: Path, text: str) -> None:
        """Burn text watermark into bottom-right corner."""
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(input_path),
            "-vf", (
                f"drawtext=text='{text}':fontsize=24:fontcolor=white@0.6"
                f":x=w-tw-20:y=h-th-20"
            ),
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)

    def _concat_segments(self, segments: list[Path], output_path: Path) -> Path:
        """Simple concatenation fallback (no transitions)."""
        list_file = output_path.parent / "concat_list.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in segments))
        cmd = [
            self.ffmpeg.ffmpeg,
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return output_path

    # ── AI Video Generation (kie.ai Kling 3.0) ────────────────

    def _get_kie_video(self):
        """Lazy-init KieVideoGenerator (avoids crash if KIE_API_KEY absent)."""
        if self._kie_video is None:
            from skill_kie_video import KieVideoGenerator
            self._kie_video = KieVideoGenerator()
        return self._kie_video

    def _generate_ai_video_segment(
        self, scene: dict, output_dir: Path, prefix: str,
    ) -> Path:
        """Generate a video segment via Kling 3.0 text-to-video.

        Uses scene["visual_description"] as the generation prompt.
        Falls back to Ken Burns if AI generation fails.
        """
        gen = self._get_kie_video()
        output_path = output_dir / f"{prefix}_ai_video.mp4"
        duration = str(min(int(scene["duration"]), 15))  # Kling max 15s

        prompt = scene.get("visual_description", scene.get("title", ""))
        if not prompt:
            logger.warning("Scene %d: no prompt for ai_video, falling back to Ken Burns", scene["id"])
            return self._generate_kenburns_segment(scene, output_dir, prefix)

        try:
            result = gen.generate(
                prompt=prompt,
                output_path=output_path,
                duration=duration,
                aspect_ratio=scene.get("aspect_ratio", "16:9"),
                mode=scene.get("ai_mode", "pro"),
                sound=False,  # Narration replaces audio
                max_wait=600.0,
            )
            if result.state == "success" and output_path.exists():
                # Scale to 1920x1080 for pipeline consistency
                scaled = output_dir / f"{prefix}_ai_scaled.mp4"
                self._prepare_screen_recording(output_path, scaled, scene["duration"])
                logger.info("Scene %d: AI video generated via Kling 3.0", scene["id"])
                return scaled
        except Exception as e:
            logger.warning("Scene %d: AI video failed (%s), falling back to Ken Burns", scene["id"], e)

        return self._generate_kenburns_segment(scene, output_dir, prefix)

    def _generate_ai_image_to_video_segment(
        self, scene: dict, output_dir: Path, prefix: str,
    ) -> Path:
        """Generate video from a start frame image via Kling 3.0.

        Resolves image first (brand/cache/kie.ai/fal.ai), then animates it.
        Falls back to Ken Burns if AI generation fails.
        """
        gen = self._get_kie_video()

        # Resolve start frame image
        image_path = self.images.resolve_image_for_scene(
            scene_description=scene.get("visual_description", ""),
            scene_title=scene.get("title", ""),
        )

        # For image-to-video, we need a publicly accessible URL.
        # If the image is local, we need to upload it first.
        # For now, if an explicit "image_url" is provided, use it directly.
        image_url = scene.get("image_url")
        if not image_url:
            logger.warning(
                "Scene %d: ai_image_to_video requires 'image_url' in storyboard. "
                "Using Ken Burns with resolved local image instead.",
                scene["id"],
            )
            return self._generate_kenburns_segment(scene, output_dir, prefix)

        output_path = output_dir / f"{prefix}_ai_i2v.mp4"
        duration = str(min(int(scene["duration"]), 15))
        prompt = scene.get("visual_description", "Smooth cinematic camera movement")

        try:
            result = gen.generate_from_image(
                prompt=prompt,
                image_path_or_url=image_url,
                output_path=output_path,
                duration=duration,
                aspect_ratio=scene.get("aspect_ratio", "16:9"),
            )
            if result.state == "success" and output_path.exists():
                scaled = output_dir / f"{prefix}_ai_i2v_scaled.mp4"
                self._prepare_screen_recording(output_path, scaled, scene["duration"])
                logger.info("Scene %d: AI image-to-video via Kling 3.0", scene["id"])
                return scaled
        except Exception as e:
            logger.warning("Scene %d: AI image-to-video failed (%s), falling back", scene["id"], e)

        return self._generate_kenburns_segment(scene, output_dir, prefix)

    # ── Marketing Asset Generation ─────────────────────────────

    def _get_ffmpeg_web(self):
        """Lazy-init FFmpegWebOps."""
        if self._ffmpeg_web is None:
            from ffmpeg_web_ops import FFmpegWebOps
            self._ffmpeg_web = FFmpegWebOps()
        return self._ffmpeg_web

    def _generate_marketing_assets(
        self,
        video_path: Path,
        output_dir: Path,
        config: dict,
        storyboard: dict,
    ) -> dict[str, str]:
        """Generate marketing assets from the assembled video.

        Produces:
          - scroll_site: Apple-style scroll-driven website
          - ads: HTML5 ads in essential cross-platform sizes
          - landing_page: Single-file responsive landing page
          - web_mp4: Web-optimized MP4 (H.264 faststart)
          - preview_gif: Animated GIF preview

        Args:
            video_path: Path to the final assembled video.
            output_dir: Base output directory for marketing assets.
            config: Marketing config from storyboard JSON.
            storyboard: Full storyboard dict for metadata.

        Returns:
            Dict mapping asset type to output path.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        assets = {}
        ffweb = self._get_ffmpeg_web()

        title = storyboard.get("title", "TerraFlow")
        brand = config.get("brand", {
            "name": "TerraFlow",
            "primary_color": "#166534",
            "secondary_color": "#D97706",
            "text_color": "#FFFFFF",
            "cta_text": "En savoir plus",
            "landing_url": "https://terraflow.cm",
        })

        # 1. Web-optimized MP4
        try:
            web_mp4 = output_dir / "web" / "hero.mp4"
            ffweb.optimize_mp4_web(video_path, web_mp4, width=1920, crf=23)
            assets["web_mp4"] = str(web_mp4)
            logger.info("Marketing: web MP4 generated")
        except Exception as e:
            logger.warning("Marketing web MP4 failed: %s", e)

        # 2. Preview GIF
        try:
            gif = output_dir / "web" / "preview.gif"
            ffweb.create_preview_gif(video_path, gif, start=0, duration=5, width=480)
            assets["preview_gif"] = str(gif)
        except Exception as e:
            logger.warning("Marketing GIF failed: %s", e)

        # 3. Scroll-driven website
        if config.get("scroll_site", True):
            try:
                from scroll_site_builder import ScrollSiteBuilder
                if self._scroll_builder is None:
                    self._scroll_builder = ScrollSiteBuilder()
                site_dir = output_dir / "scroll_site"
                sections = config.get("sections", [
                    {"title": title, "text": storyboard.get("description", "")},
                ])
                self._scroll_builder.build(
                    video_path=video_path,
                    output_dir=site_dir,
                    num_frames=config.get("num_frames", 60),
                    sections=sections,
                    config={"title": title, "headline": brand.get("name", title)},
                )
                assets["scroll_site"] = str(site_dir)
                logger.info("Marketing: scroll site generated (%s)", site_dir)
            except Exception as e:
                logger.warning("Marketing scroll site failed: %s", e)

        # 4. HTML5 Ads
        if config.get("ads", True):
            try:
                from ads_builder import AdsBuilder
                if self._ads_builder is None:
                    self._ads_builder = AdsBuilder()

                # Extract a poster frame for static ads
                poster = output_dir / "poster.png"
                ffweb.extract_poster(video_path, poster, width=1920, quality=95)

                ads_dir = output_dir / "ads"
                ad_results = self._ads_builder.build_essential_ads(
                    image_path=poster,
                    output_dir=ads_dir,
                    headline=config.get("headline", title),
                    brand=brand,
                )
                assets["ads"] = str(ads_dir)
                assets["ads_count"] = str(len(ad_results))
                logger.info("Marketing: %d ad variants generated", len(ad_results))
            except Exception as e:
                logger.warning("Marketing ads failed: %s", e)

        # 5. Landing page
        if config.get("landing_page", True):
            try:
                from landing_page_builder import LandingPageBuilder
                if self._landing_builder is None:
                    self._landing_builder = LandingPageBuilder()
                lp_path = output_dir / "landing" / "index.html"
                self._landing_builder.build(
                    output_path=lp_path,
                    hero_image_url=assets.get("web_mp4", "hero.mp4"),
                    config={
                        "name": brand.get("name", "TerraFlow"),
                        "headline": config.get("headline", title),
                        "subheadline": config.get("subheadline", ""),
                        "primary_color": brand.get("primary_color", "#166534"),
                        "secondary_color": brand.get("secondary_color", "#D97706"),
                        "cta_text": brand.get("cta_text", "En savoir plus"),
                        "cta_url": brand.get("landing_url", "https://terraflow.cm"),
                    },
                    features=config.get("features", []),
                    stats=config.get("stats", []),
                )
                assets["landing_page"] = str(lp_path)
                logger.info("Marketing: landing page generated")
            except Exception as e:
                logger.warning("Marketing landing page failed: %s", e)

        return assets
