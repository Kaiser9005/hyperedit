"""Batch processor — chains multiple video editing skills into a pipeline."""

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance
from notification_service import NotificationService
from e2e_verifier import E2EVerifier, VerificationConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    skill_name: str
    config: dict = field(default_factory=dict)
    required: bool = True  # If False, failure doesn't stop pipeline


@dataclass
class PipelineResult:
    success: bool
    steps_completed: int
    steps_total: int
    input_path: str
    output_path: str
    duration_seconds: float
    step_results: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    qa_score: Optional[float] = None


class BatchProcessor:
    """Chain multiple video skills into an automated pipeline."""

    # Registry of skill name -> (module, class, method defaults)
    SKILL_REGISTRY = {
        "dead_air": {"module": "skill_dead_air", "class": "DeadAirRemoval", "defaults": {}},
        "captions": {"module": "skill_captions", "class": "CaptionGeneration", "defaults": {"burn_in": False}},
        "audio": {"module": "skill_audio", "class": "AudioEnhancement", "defaults": {}},
        "color": {"module": "skill_color", "class": "ColorGrading", "defaults": {"preset": "cinematic"}},
        "brand": {"module": "skill_brand", "class": "BrandKitManager", "defaults": {}},
        "transitions": {"module": "skill_transitions", "class": "TransitionManager", "defaults": {}},
        "style": {"module": "skill_style", "class": "StyleTransfer", "defaults": {"style": "cinematic_teal_orange"}},
        "animation": {"module": "skill_animation", "class": "AnimationOverlay", "defaults": {"overlays": []}},
        "broll": {"module": "skill_broll", "class": "BRollInserter", "defaults": {}},
    }

    # Non-pipeline skills (different I/O signatures, not video-in/video-out):
    # chapters, thumbnail, gif, shortform, export, script, voiceover, youtube, template

    # Skills that use output_dir instead of output_path
    _DIR_OUTPUT_SKILLS = {"captions"}

    # Default pipeline order
    DEFAULT_PIPELINE = ["dead_air", "audio", "color", "captions"]

    def __init__(self, notifier: Optional[NotificationService] = None):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()
        self.verifier = E2EVerifier()
        self.notifier = notifier or NotificationService()
        self._skill_cache = {}

    def execute(
        self,
        input_path: Path,
        output_dir: Path,
        steps: Optional[list[PipelineStep]] = None,
    ) -> PipelineResult:
        """Execute a full pipeline on a video.

        Args:
            input_path: Source video file.
            output_dir: Directory for intermediate and final outputs.
            steps: Ordered list of PipelineStep to execute.
                   Uses DEFAULT_PIPELINE if None.

        Returns:
            PipelineResult with success status, step results, and errors.
        """
        start_time = time.time()
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        # Use default pipeline if no steps provided
        if steps is None:
            steps = [PipelineStep(skill_name=s) for s in self.DEFAULT_PIPELINE]

        self.notifier.pipeline_started(
            input_path.name,
            [s.skill_name for s in steps],
        )

        # Pipeline state
        current_input = input_path
        step_results = []
        errors = []
        completed = 0

        for i, step in enumerate(steps):
            step_output = output_dir / f"step_{i:02d}_{step.skill_name}{input_path.suffix}"

            self.notifier.skill_started(step.skill_name, str(current_input))

            try:
                result = self._execute_step(step, current_input, step_output)
                step_results.append({
                    "step": i,
                    "skill": step.skill_name,
                    "success": True,
                    "result": result,
                })
                self.notifier.skill_completed(step.skill_name, result)
                current_input = step_output
                completed += 1
            except Exception as e:
                error_msg = f"{step.skill_name}: {str(e)}"
                errors.append(error_msg)
                step_results.append({
                    "step": i,
                    "skill": step.skill_name,
                    "success": False,
                    "error": str(e),
                })
                self.notifier.skill_failed(step.skill_name, str(e))

                if step.required:
                    logger.error(f"Required step failed: {error_msg}")
                    break
                else:
                    logger.warning(f"Optional step failed (continuing): {error_msg}")
                    # Keep current_input unchanged for next step

        # Copy final output to named file
        final_output = output_dir / f"{input_path.stem}_processed{input_path.suffix}"
        if current_input != input_path and current_input.exists():
            shutil.copy2(current_input, final_output)
        else:
            final_output = input_path  # No processing happened

        # === POST-PIPELINE QA ===
        qa_results = []
        if final_output != input_path and final_output.exists():
            try:
                input_meta = self.ffmpeg.get_metadata(input_path)
                qa_results = self.qa.full_check(
                    final_output,
                    expected_duration=input_meta.duration,
                    min_width=input_meta.width,
                    min_height=input_meta.height,
                )
            except (ValueError, FileNotFoundError) as e:
                logger.warning(f"Pipeline QA check failed: {e}")

        # === E2E SCORED VERIFICATION (V-I-V Principe 5: Tolerance Zero) ===
        qa_report = None
        if final_output != input_path and final_output.exists():
            try:
                job_id = f"{input_path.stem}_{int(time.time())}"
                config = VerificationConfig(
                    expected_duration=input_meta.duration if qa_results else None,
                    min_width=1920,
                    min_height=1080,
                )
                qa_report = self.verifier.verify_pipeline_output(job_id, final_output, config)
                if not qa_report.passed:
                    logger.warning("E2E score %.1f/10 < threshold — needs review", qa_report.score)
            except Exception as e:
                logger.warning("E2E verification failed: %s", e)

        elapsed = time.time() - start_time
        success = completed == len(steps) or (completed > 0 and len(errors) == 0)

        self.notifier.pipeline_completed(input_path.name, elapsed)

        return PipelineResult(
            success=success,
            steps_completed=completed,
            steps_total=len(steps),
            input_path=str(input_path),
            output_path=str(final_output),
            duration_seconds=round(elapsed, 2),
            step_results=step_results,
            errors=errors,
            qa_score=qa_report.score if qa_report else None,
        )

    def _execute_step(self, step: PipelineStep, input_path: Path, output_path: Path) -> dict:
        """Execute a single pipeline step."""
        reg = self.SKILL_REGISTRY.get(step.skill_name)
        if not reg:
            raise ValueError(
                f"Unknown skill: {step.skill_name}. "
                f"Available: {list(self.SKILL_REGISTRY.keys())}"
            )

        # Lazy-load skill class
        skill = self._get_skill(step.skill_name, reg)

        # Merge defaults with step config
        config = {**reg["defaults"], **step.config}

        # Some skills use output_dir instead of output_path (e.g. captions)
        if step.skill_name in self._DIR_OUTPUT_SKILLS:
            return skill.execute(input_path=input_path, output_dir=output_path.parent, **config)

        # Standard call: input_path + output_path + config
        return skill.execute(input_path=input_path, output_path=output_path, **config)

    def _get_skill(self, name: str, reg: dict):
        """Lazy-load and cache a skill instance."""
        if name not in self._skill_cache:
            import importlib
            module = importlib.import_module(reg["module"])
            cls = getattr(module, reg["class"])
            self._skill_cache[name] = cls()
        return self._skill_cache[name]

    def list_skills(self) -> list[str]:
        """List available skills."""
        return list(self.SKILL_REGISTRY.keys())

    def get_default_pipeline(self) -> list[str]:
        """Get the default pipeline order."""
        return self.DEFAULT_PIPELINE.copy()
