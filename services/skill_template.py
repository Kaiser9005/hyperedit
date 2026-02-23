"""Skill 12: Template Engine.

Apply video structure templates (intro/outro/sections) to calculate timing plans.
Supports built-in templates and custom JSON template files.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


BUILT_IN_TEMPLATES = {
    "corporate_ad": {
        "name": "Corporate Advertisement",
        "sections": [
            {"type": "intro", "duration": 3, "label": "Brand intro"},
            {"type": "content", "duration": None, "label": "Main content"},
            {"type": "cta", "duration": 5, "label": "Call to action"},
            {"type": "outro", "duration": 3, "label": "Brand outro"},
        ],
    },
    "tutorial": {
        "name": "Tutorial Video",
        "sections": [
            {"type": "intro", "duration": 5, "label": "Introduction"},
            {"type": "content", "duration": None, "label": "Tutorial steps"},
            {"type": "recap", "duration": 5, "label": "Summary"},
            {"type": "outro", "duration": 3, "label": "Subscribe CTA"},
        ],
    },
    "social_short": {
        "name": "Social Media Short",
        "sections": [
            {"type": "hook", "duration": 3, "label": "Attention hook"},
            {"type": "content", "duration": None, "label": "Core message"},
            {"type": "cta", "duration": 2, "label": "Action prompt"},
        ],
    },
    "product_demo": {
        "name": "Product Demo",
        "sections": [
            {"type": "intro", "duration": 3, "label": "Problem statement"},
            {"type": "demo", "duration": None, "label": "Product demonstration"},
            {"type": "features", "duration": 10, "label": "Feature highlights"},
            {"type": "cta", "duration": 5, "label": "Where to buy"},
        ],
    },
}


class TemplateEngine:
    """Calculate video timing plans based on structure templates."""

    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        template_name: str = "corporate_ad",
        custom_template: Optional[Path] = None,
    ) -> dict:
        """Full V-I-V cycle for template timing plan generation.

        Args:
            input_path: Path to the input video file.
            output_path: Path for output (not written; plan only).
            template_name: Name of a built-in template.
            custom_template: Path to a custom template JSON file.

        Returns:
            Dict with template_name, sections list (type, start, end,
            duration, label), and total_duration.
        """
        # === VERIFY (Before) ===
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        meta = self.ffmpeg.get_metadata(input_path)
        total_duration = meta.duration

        # === IMPLEMENT ===
        template = self.load_template(
            template_name=template_name,
            template_path=custom_template,
        )

        planned_sections = self.plan_sections(template, total_duration)

        # === VERIFY (After) ===
        planned_total = sum(s["duration"] for s in planned_sections)
        if abs(planned_total - total_duration) > 0.01:
            raise ValueError(
                f"Section durations ({planned_total:.2f}s) do not sum to "
                f"input duration ({total_duration:.2f}s)"
            )

        name = template.get("name", template_name)

        return {
            "template_name": name,
            "sections": planned_sections,
            "total_duration": total_duration,
        }

    def load_template(
        self,
        template_name: Optional[str] = None,
        template_path: Optional[Path] = None,
    ) -> dict:
        """Load a built-in template by name or a custom template from JSON.

        Args:
            template_name: Key in BUILT_IN_TEMPLATES.
            template_path: Path to a custom JSON template file.

        Returns:
            Template dict with 'name' and 'sections' keys.

        Raises:
            ValueError: If template_name is not found in built-in templates.
            FileNotFoundError: If template_path does not exist.
        """
        if template_path is not None:
            path = Path(template_path)
            if not path.exists():
                raise FileNotFoundError(f"Template file not found: {path}")
            with open(path) as f:
                return json.load(f)

        if template_name is None:
            template_name = "corporate_ad"

        if template_name not in BUILT_IN_TEMPLATES:
            raise ValueError(
                f"Unknown template '{template_name}'. "
                f"Available: {', '.join(BUILT_IN_TEMPLATES.keys())}"
            )

        # Return a deep copy so callers cannot mutate the built-in dict
        import copy
        return copy.deepcopy(BUILT_IN_TEMPLATES[template_name])

    def plan_sections(
        self,
        template: dict,
        total_duration: float,
    ) -> list[dict]:
        """Distribute time across template sections.

        Fixed-duration sections keep their specified durations.
        Variable-duration sections (duration=None) share the remaining
        time equally.  When total_duration is shorter than the sum of
        fixed durations, all sections are scaled proportionally.

        Args:
            template: Template dict with a 'sections' list.
            total_duration: Total video duration in seconds.

        Returns:
            List of dicts with type, start, end, duration, and label.
        """
        sections = template["sections"]

        fixed_total = sum(
            s["duration"] for s in sections if s["duration"] is not None
        )
        variable_count = sum(
            1 for s in sections if s["duration"] is None
        )

        if variable_count > 0:
            remaining = total_duration - fixed_total
            variable_duration = max(remaining / variable_count, 0)
        else:
            variable_duration = 0

        # If the video is too short for fixed sections and there are no
        # variable sections, scale all fixed sections proportionally.
        if variable_count == 0 and fixed_total > 0:
            scale = total_duration / fixed_total
        else:
            scale = 1.0

        planned = []
        cursor = 0.0

        for s in sections:
            if s["duration"] is None:
                dur = variable_duration
            else:
                dur = s["duration"] * scale

            planned.append({
                "type": s["type"],
                "start": round(cursor, 4),
                "end": round(cursor + dur, 4),
                "duration": round(dur, 4),
                "label": s["label"],
            })
            cursor += dur

        return planned

    def save_template(self, template: dict, output_path: Path) -> Path:
        """Save a template dict as a JSON file.

        Args:
            template: Template dict with 'name' and 'sections' keys.
            output_path: Destination path for the JSON file.

        Returns:
            Path to the saved file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(template, f, indent=2)
        return output_path

    def list_templates(self) -> dict:
        """Return the dictionary of built-in templates.

        Returns:
            Dict mapping template keys to their definitions.
        """
        import copy
        return copy.deepcopy(BUILT_IN_TEMPLATES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Template Engine")
    parser.add_argument("--input", default=None, help="Input video path")
    parser.add_argument("--output", default=None, help="Output path (plan only)")
    parser.add_argument(
        "--template",
        default="corporate_ad",
        help="Built-in template name",
    )
    parser.add_argument(
        "--custom-template",
        default=None,
        help="Path to custom template JSON",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available built-in templates",
    )

    args = parser.parse_args()
    engine = TemplateEngine()

    if args.list:
        templates = engine.list_templates()
        print("\n=== Built-in Templates ===")
        for key, tpl in templates.items():
            section_types = [s["type"] for s in tpl["sections"]]
            print(f"  {key}: {tpl['name']} [{' -> '.join(section_types)}]")
    elif args.input:
        result = engine.execute(
            input_path=Path(args.input),
            output_path=Path(args.output or "plan_output.mp4"),
            template_name=args.template,
            custom_template=Path(args.custom_template) if args.custom_template else None,
        )
        print(f"\n=== Template Plan: {result['template_name']} ===")
        print(f"Total duration: {result['total_duration']:.1f}s\n")
        for s in result["sections"]:
            print(
                f"  [{s['start']:6.1f}s - {s['end']:6.1f}s] "
                f"{s['type']:12s} ({s['duration']:.1f}s) {s['label']}"
            )
    else:
        parser.print_help()
