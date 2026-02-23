"""Skill 18: Voiceover Generation.

Generate voiceover audio from text using ElevenLabs TTS API.
Supports merging generated audio with existing video via FFmpeg.
"""

import argparse
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from ffmpeg_service import FFmpegService


class VoiceoverGenerator:
    """Generate voiceover audio from text and optionally merge with video."""

    VOICES = {
        "narrator_male": {
            "voice_id": "pNInz6obpgDQGcFmaJgB",
            "name": "Adam",
            "style": "narrative",
        },
        "narrator_female": {
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
            "name": "Sarah",
            "style": "narrative",
        },
        "professional": {
            "voice_id": "onwK4e9ZLuTAKqWW03F9",
            "name": "Daniel",
            "style": "professional",
        },
        "friendly": {
            "voice_id": "jBpfuIE2acCO8z3wKNLl",
            "name": "Emily",
            "style": "friendly",
        },
        "energetic": {
            "voice_id": "yoZ06aMxZJJ28mfd3POQ",
            "name": "Sam",
            "style": "energetic",
        },
    }

    def __init__(self):
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.api_key = api_key
        self.enabled = bool(api_key)
        self.ffmpeg = FFmpegService()

    def execute(
        self,
        text: str,
        output_path: Path,
        voice: str = "narrator_male",
        video_path: Optional[Path] = None,
        merge_with_video: bool = True,
    ) -> dict:
        """Full V-I-V cycle for voiceover generation.

        Args:
            text: The script/text to convert to speech.
            output_path: Path for the output audio or merged video file.
            voice: Voice preset name from VOICES dict.
            video_path: Optional video file to merge voiceover into.
            merge_with_video: Whether to merge generated audio with video.

        Returns:
            Dict with audio_path, video_path (if merged), voice_used,
            text_length, and duration.
        """
        # === VERIFY (Before) ===
        if not text or not text.strip():
            raise ValueError("Text must not be empty")

        if voice not in self.VOICES:
            raise ValueError(
                f"Unknown voice '{voice}'. Available: {list(self.VOICES.keys())}"
            )

        voice_info = self.VOICES[voice]
        estimated_duration = self._estimate_duration(text)

        # === IMPLEMENT ===
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        # Determine audio output path
        if video_path and merge_with_video:
            audio_path = work_dir / f"{output_path.stem}_voiceover.wav"
        else:
            audio_path = output_path

        # Generate audio (API call or placeholder)
        if self.enabled:
            self._generate_audio(text, voice_info["voice_id"], audio_path)
        else:
            self._generate_silence_placeholder(estimated_duration, audio_path)

        # Merge with video if requested
        merged_video_path = None
        if video_path and merge_with_video:
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            merged_video_path = output_path
            self.ffmpeg.merge_audio(
                video_path=Path(video_path),
                audio_path=audio_path,
                output_path=merged_video_path,
                audio_volume=1.0,
            )

        # === VERIFY (After) ===
        if merged_video_path:
            if not merged_video_path.exists():
                raise RuntimeError(
                    f"Merged video was not created: {merged_video_path}"
                )
        else:
            if not audio_path.exists():
                raise RuntimeError(f"Audio file was not created: {audio_path}")

        # Get actual duration from generated audio
        actual_duration = estimated_duration
        try:
            if audio_path.exists():
                meta = self.ffmpeg.get_metadata(audio_path)
                actual_duration = meta.duration
        except (ValueError, subprocess.CalledProcessError):
            # Audio-only files may not report duration via ffprobe; use estimate
            logging.getLogger(__name__).debug(
                "Could not read audio metadata for %s, using estimate %.1fs",
                audio_path, estimated_duration,
            )

        result = {
            "audio_path": str(audio_path),
            "voice_used": voice_info["name"],
            "text_length": len(text),
            "duration": actual_duration,
        }

        if merged_video_path:
            result["video_path"] = str(merged_video_path)

        return result

    def _generate_audio(
        self, text: str, voice_id: str, output_path: Path
    ) -> Path:
        """Generate speech audio via ElevenLabs API.

        This is a placeholder for the actual ElevenLabs API integration.
        Implement with the ElevenLabs Python SDK or REST API when ready.

        Raises:
            NotImplementedError: Always, until ElevenLabs integration is wired up.
        """
        raise NotImplementedError(
            "ElevenLabs API integration not yet implemented. "
            "Set ELEVENLABS_API_KEY and implement this method with the "
            "ElevenLabs Python SDK (elevenlabs.io)."
        )

    def _generate_silence_placeholder(
        self, duration: float, output_path: Path
    ) -> Path:
        """Create a silent WAV file of the given duration via FFmpeg.

        Useful for testing the pipeline without an API key.

        Args:
            duration: Length of silence in seconds.
            output_path: Path for the output WAV file.

        Returns:
            Path to the created silent WAV file.
        """
        cmd = [
            self.ffmpeg.ffmpeg,
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:a", "pcm_s16le",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _estimate_duration(self, text: str) -> float:
        """Estimate speech duration from text length.

        Uses ~150 words per minute (2.5 words per second) as the baseline.

        Args:
            text: The input text.

        Returns:
            Estimated duration in seconds.
        """
        words = text.split()
        word_count = len(words)
        if word_count == 0:
            return 0.0
        return word_count / 2.5

    def list_voices(self) -> dict:
        """Return available voice presets.

        Returns:
            Copy of the VOICES dictionary.
        """
        return dict(self.VOICES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate voiceover from text")
    parser.add_argument("--text", required=True, help="Text to convert to speech")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument(
        "--voice",
        default="narrator_male",
        choices=list(VoiceoverGenerator.VOICES.keys()),
        help="Voice preset to use",
    )
    parser.add_argument("--video", default=None, help="Video file to merge with")
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip merging audio with video",
    )

    args = parser.parse_args()

    generator = VoiceoverGenerator()
    result = generator.execute(
        text=args.text,
        output_path=Path(args.output),
        voice=args.voice,
        video_path=Path(args.video) if args.video else None,
        merge_with_video=not args.no_merge,
    )

    print("\n=== Voiceover Generation Complete ===")
    print(f"Voice: {result['voice_used']}")
    print(f"Text length: {result['text_length']} chars")
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Audio: {result['audio_path']}")
    if "video_path" in result:
        print(f"Video: {result['video_path']}")
