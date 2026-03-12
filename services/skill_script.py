"""Skill 13: Script & Storyboard Generation.

Generates video scripts and storyboards from a text brief or existing video.
Uses whisper.cpp for video analysis and produces structured storyboard JSON.
"""

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from whisper_service import WhisperService


# Style templates define the tone and structure for each video style
STYLE_TEMPLATES = {
    "corporate": {
        "tone": "professional and authoritative",
        "scenes_range": (4, 6),
        "typical_structure": ["intro/hook", "problem statement", "solution", "key benefits", "call to action"],
    },
    "social": {
        "tone": "casual and engaging",
        "scenes_range": (3, 5),
        "typical_structure": ["hook", "main content", "engagement prompt"],
    },
    "tutorial": {
        "tone": "clear and instructional",
        "scenes_range": (4, 7),
        "typical_structure": ["intro", "setup", "step-by-step", "recap", "next steps"],
    },
    "ad": {
        "tone": "persuasive and dynamic",
        "scenes_range": (3, 5),
        "typical_structure": ["attention hook", "value proposition", "social proof", "call to action"],
    },
}


class ScriptGenerator:
    """Generate video scripts and storyboards from briefs or existing video."""

    def __init__(self):
        self.whisper = WhisperService()

    def execute(
        self,
        brief: str,
        output_path: Path,
        video_input: Optional[Path] = None,
        target_duration: float = 60,
        style: str = "corporate",
        language: str = "en",
    ) -> dict:
        """
        Full V-I-V cycle for script and storyboard generation.

        Returns dict with: panels_count, total_duration, style, language, output_path
        """
        # === VERIFY (Before) ===
        if not brief or not brief.strip():
            raise ValueError("Brief cannot be empty")

        if video_input is not None and not Path(video_input).exists():
            raise FileNotFoundError(f"Video input not found: {video_input}")

        if target_duration <= 0:
            raise ValueError(f"Target duration must be positive, got {target_duration}")

        if style not in STYLE_TEMPLATES:
            raise ValueError(
                f"Unknown style '{style}'. Choose from: {', '.join(STYLE_TEMPLATES.keys())}"
            )

        # === IMPLEMENT ===
        transcript = None
        if video_input is not None:
            transcription = self.whisper.transcribe_video(
                Path(video_input), language=language
            )
            transcript = transcription.text

        # Try LLM generation first, fall back to template
        try:
            prompt = self._build_prompt(brief, style, language, transcript=transcript)
            script_text = self._generate_script_from_llm(prompt)
            panels = self._parse_script_to_storyboard(script_text, target_duration)
        except NotImplementedError:
            panels = self._generate_template_script(
                brief, style, target_duration, language
            )

        # Save storyboard
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._save_storyboard(panels, output)

        # === VERIFY (After) ===
        if not panels:
            raise RuntimeError("Storyboard generation produced no panels")

        total_duration = sum(p["duration"] for p in panels)
        if total_duration <= 0:
            raise RuntimeError("Storyboard total duration is zero or negative")

        return {
            "panels_count": len(panels),
            "total_duration": total_duration,
            "style": style,
            "language": language,
            "output_path": str(output),
        }

    def _build_prompt(
        self,
        brief: str,
        style: str,
        language: str,
        transcript: Optional[str] = None,
    ) -> str:
        """Build the prompt for LLM-based script generation."""
        template = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["corporate"])
        structure = ", ".join(template["typical_structure"])

        prompt_parts = [
            f"Generate a video script for the following brief:",
            f"",
            f"Brief: {brief}",
            f"",
            f"Style: {style} ({template['tone']})",
            f"Language: {language}",
            f"Suggested structure: {structure}",
            f"",
        ]

        if transcript:
            prompt_parts.extend([
                f"Existing video transcript for reference:",
                f"{transcript}",
                f"",
            ])

        prompt_parts.extend([
            f"Output format: For each scene, provide:",
            f"SCENE [number]: [title]",
            f"VISUAL: [description of what the viewer sees]",
            f"AUDIO: [narration, dialogue, or sound design]",
            f"TEXT: [on-screen text or titles]",
            f"NOTES: [production notes]",
            f"",
            f"Create {template['scenes_range'][0]}-{template['scenes_range'][1]} scenes.",
        ])

        return "\n".join(prompt_parts)

    def _generate_script_from_llm(self, prompt: str) -> str:
        """Generate script via Claude API.

        Uses Anthropic Claude for intelligent script generation with
        African storytelling and FOFAL agricultural context awareness.

        Args:
            prompt: The formatted script generation prompt.

        Returns:
            Raw script text in SCENE format.
        """
        import httpx
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — cannot generate script")

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    def _parse_script_to_storyboard(
        self, script_text: str, target_duration: float
    ) -> list[dict]:
        """Parse LLM-generated script text into storyboard panels.

        Expects script in the format:
            SCENE 1: Title
            VISUAL: description
            AUDIO: description
            TEXT: description
            NOTES: description
        """
        panels = []
        scene_pattern = re.compile(
            r"SCENE\s+(\d+)\s*:\s*(.*?)(?=SCENE\s+\d+|$)",
            re.DOTALL | re.IGNORECASE,
        )

        scenes = scene_pattern.findall(script_text)
        if not scenes:
            return []

        num_scenes = len(scenes)
        scene_duration = target_duration / num_scenes

        for i, (scene_num, scene_content) in enumerate(scenes):
            visual = self._extract_field(scene_content, "VISUAL")
            audio = self._extract_field(scene_content, "AUDIO")
            text = self._extract_field(scene_content, "TEXT")
            notes = self._extract_field(scene_content, "NOTES")

            start = i * scene_duration
            end = start + scene_duration

            panels.append({
                "scene": int(scene_num),
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(scene_duration, 2),
                "visual": visual,
                "audio": audio,
                "text": text,
                "notes": notes,
            })

        return panels

    def _extract_field(self, content: str, field_name: str) -> str:
        """Extract a field value from scene content."""
        pattern = re.compile(
            rf"{field_name}\s*:\s*(.*?)(?=(?:VISUAL|AUDIO|TEXT|NOTES)\s*:|$)",
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(content)
        if match:
            return match.group(1).strip()
        return ""

    def _generate_template_script(
        self,
        brief: str,
        style: str,
        target_duration: float,
        language: str,
    ) -> list[dict]:
        """Generate a template-based script from the brief without LLM.

        Splits the brief into key phrases and creates scenes with equal
        duration, following the style's typical structure.
        """
        template = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["corporate"])
        structure = template["typical_structure"]
        num_scenes = len(structure)

        # Clamp to style range
        min_scenes, max_scenes = template["scenes_range"]
        num_scenes = max(min_scenes, min(num_scenes, max_scenes))
        structure = structure[:num_scenes]

        scene_duration = target_duration / num_scenes

        # Split brief into meaningful phrases for distribution across scenes
        phrases = self._split_brief(brief, num_scenes)

        panels = []
        for i, section_name in enumerate(structure):
            phrase = phrases[i] if i < len(phrases) else brief
            start = round(i * scene_duration, 2)
            end = round(start + scene_duration, 2)

            panels.append({
                "scene": i + 1,
                "start": start,
                "end": end,
                "duration": round(scene_duration, 2),
                "visual": f"[{section_name.title()}] {phrase}",
                "audio": self._audio_cue_for_section(section_name, style, language),
                "text": self._text_overlay_for_section(section_name, phrase),
                "notes": f"Style: {style}, Section: {section_name}",
            })

        return panels

    def _split_brief(self, brief: str, num_parts: int) -> list[str]:
        """Split the brief into roughly equal parts for scene distribution."""
        # Split on sentence boundaries or commas
        sentences = re.split(r"[.!?;]+", brief)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [brief] * num_parts

        if len(sentences) >= num_parts:
            # Distribute sentences across parts
            chunk_size = math.ceil(len(sentences) / num_parts)
            parts = []
            for i in range(0, len(sentences), chunk_size):
                chunk = sentences[i : i + chunk_size]
                parts.append(". ".join(chunk))
            # Pad if needed
            while len(parts) < num_parts:
                parts.append(sentences[-1])
            return parts[:num_parts]
        else:
            # Fewer sentences than scenes: repeat and distribute
            parts = []
            for i in range(num_parts):
                parts.append(sentences[i % len(sentences)])
            return parts

    def _audio_cue_for_section(
        self, section: str, style: str, language: str
    ) -> str:
        """Generate an audio cue description based on section type."""
        cues = {
            "intro": "Background music fades in, narrator introduces topic",
            "intro/hook": "Upbeat music, strong opening narration",
            "hook": "Attention-grabbing sound effect, quick narration",
            "attention hook": "Bold sound design, punchy voiceover",
            "problem statement": "Subtle tension in music, narrator describes challenge",
            "solution": "Music shifts to positive tone, narrator presents solution",
            "main content": "Clear narration over ambient music",
            "key benefits": "Energetic music, narrator highlights advantages",
            "value proposition": "Confident narration, subtle background music",
            "social proof": "Testimonial audio or narrator citing results",
            "call to action": "Music builds to crescendo, clear call to action",
            "engagement prompt": "Direct address to viewer, upbeat closing",
            "setup": "Calm narration explaining prerequisites",
            "step-by-step": "Clear instructional narration, minimal music",
            "recap": "Summary narration, music returns",
            "next steps": "Encouraging narration, music fades out",
        }
        section_lower = section.lower()
        return cues.get(section_lower, f"Narration for {section}")

    def _text_overlay_for_section(self, section: str, phrase: str) -> str:
        """Generate a text overlay suggestion for a section."""
        section_lower = section.lower()
        if "hook" in section_lower or "intro" in section_lower:
            return f"Title: {phrase[:50]}"
        elif "call to action" in section_lower:
            return f"CTA: {phrase[:40]}"
        elif "step" in section_lower:
            return f"Step: {phrase[:60]}"
        else:
            return f"{phrase[:60]}"

    def _save_storyboard(
        self, panels: list[dict], output_path: Path
    ) -> Path:
        """Save storyboard panels as structured JSON."""
        total_duration = sum(p["duration"] for p in panels)

        storyboard = {
            "metadata": {
                "total_duration": round(total_duration, 2),
                "panels_count": len(panels),
                "generated_at": datetime.utcnow().isoformat(),
            },
            "panels": panels,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(storyboard, f, indent=2, ensure_ascii=False)

        return output_path

    def generate_from_video(
        self,
        video_path: Path,
        output_path: Path,
        style: str = "corporate",
        language: str = "en",
    ) -> dict:
        """Convenience method: transcribe a video, then generate an improved script.

        Transcribes the video first, uses the transcript as the brief,
        and generates a storyboard from it.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Transcribe
        transcription = self.whisper.transcribe_video(video_path, language=language)
        brief = transcription.text

        # Use transcript duration as target
        target_duration = transcription.duration if transcription.duration > 0 else 60

        return self.execute(
            brief=brief,
            output_path=Path(output_path),
            target_duration=target_duration,
            style=style,
            language=language,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate video script and storyboard"
    )
    parser.add_argument("--brief", required=True, help="Text brief for the video")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--video", default=None, help="Optional video to analyze")
    parser.add_argument("--duration", type=float, default=60, help="Target duration (s)")
    parser.add_argument("--style", default="corporate",
                        choices=["corporate", "social", "tutorial", "ad"])
    parser.add_argument("--language", default="en")

    args = parser.parse_args()

    skill = ScriptGenerator()
    result = skill.execute(
        brief=args.brief,
        output_path=Path(args.output),
        video_input=Path(args.video) if args.video else None,
        target_duration=args.duration,
        style=args.style,
        language=args.language,
    )

    print(f"\n=== Script & Storyboard Generation Complete ===")
    print(f"Panels: {result['panels_count']}")
    print(f"Total duration: {result['total_duration']:.1f}s")
    print(f"Style: {result['style']}")
    print(f"Output: {result['output_path']}")
