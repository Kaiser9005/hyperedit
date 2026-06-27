#!/usr/bin/env python3
"""
Batch render machine presentation videos from storyboard JSONs.

Usage:
    python scripts/render_machine_videos.py                    # All 9 videos
    python scripts/render_machine_videos.py --machine cuiseur  # Single machine
    python scripts/render_machine_videos.py --global-only      # Investor video only
    python scripts/render_machine_videos.py --dry-run          # Verify renders only

Audio pipeline (professional grade):
    1. Generate voiceover FIRST (ElevenLabs TTS)
    2. Probe voiceover duration → set Ken Burns to max(scene_dur, vo_dur)
    3. Normalize ALL audio to 48kHz stereo AAC before any merge
    4. Pad audio with silence (apad) to match video exactly
    5. Final EBU R128 loudnorm pass on concatenated output
    6. +genpts +faststart flags for seamless playback

Requires:
    - FFmpeg 6+ installed
    - ElevenLabs API key in ELEVENLABS_API_KEY env var (or ~/hyperedit-ai/.env)
    - Renders in palm-oil-machinery/assets/renders/
    - Pillow (pip install Pillow)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Audio pipeline constants ──────────────────────────────────────────
AUDIO_SAMPLE_RATE = 48000   # Professional video standard (NOT 44100 CD)
AUDIO_CHANNELS = 2          # Stereo everywhere
AUDIO_BITRATE = "192k"      # High quality AAC
AUDIO_CODEC = "aac"
VIDEO_FPS = 30
VIDEO_CRF = 18              # Visually lossless

# ── Load .env ─────────────────────────────────────────────────────────
if not os.getenv("ELEVENLABS_API_KEY"):
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

STORYBOARD_DIR = Path(__file__).parent.parent / "templates" / "storyboards" / "palm_oil_machines"
RENDER_DIR = Path(os.path.expanduser(
    "~/modules-rh-authentification-expert-00-9/palm-oil-machinery/assets/renders"
))
OUTPUT_DIR = Path(os.path.expanduser(
    "~/modules-rh-authentification-expert-00-9/palm-oil-machinery/docs/videos"
))

MACHINES = [
    "cuiseur_E001", "egrappoir_E002", "digesteur-presse_E003",
    "clarification_E004", "concasseur_E005", "chaudiere_E006",
    "gazeificateur_E007", "presse-palmiste_E008",
]


# ══════════════════════════════════════════════════════════════════════
# AUDIO PIPELINE — professional grade, zero gaps
# ══════════════════════════════════════════════════════════════════════

def _probe_duration(filepath):
    """Get duration in seconds from any media file."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_format", "-print_format", "json", str(filepath)],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


def _normalize_audio(input_path, output_path):
    """Normalize any audio to pipeline standard: 48kHz stereo AAC.

    This is THE critical function — every audio source MUST pass through
    this before being merged with video or concatenated. Eliminates
    sample rate mismatches, channel count mismatches, and codec differences.
    """
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"aresample={AUDIO_SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo",
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _generate_silence(duration, output_path):
    """Generate silent audio matching pipeline standard exactly."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_SAMPLE_RATE}:cl=stereo",
        "-t", str(duration),
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def generate_voiceover(text, output_path, voice="professional"):
    """Generate TTS then normalize to pipeline standard."""
    from skill_voiceover import VoiceoverGenerator
    gen = VoiceoverGenerator()

    # Generate raw TTS (MP3, likely 44100Hz mono)
    raw_path = Path(str(output_path) + ".raw.mp3")
    gen.execute(
        text=text,
        output_path=raw_path,
        voice=voice,
        merge_with_video=False,
    )

    # Normalize to pipeline standard (48kHz stereo AAC)
    _normalize_audio(raw_path, output_path)
    raw_path.unlink(missing_ok=True)

    return _probe_duration(output_path)


def apply_ken_burns(image_path, output_path, duration, direction="slow_zoom_in"):
    """Apply Ken Burns effect via FFmpeg zoompan.

    Outputs video-only (no audio) at exactly `duration` seconds.
    """
    fps = VIDEO_FPS
    total_frames = int(duration * fps)
    w, h = 1920, 1080

    zoom_filters = {
        "slow_zoom_in": f"zoompan=z='1.0+0.0015*in':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "zoom_out": f"zoompan=z='1.3-0.0015*in':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "pan_left": f"zoompan=z='1.1':d={total_frames}:x='iw*0.1+iw*0.2*in/{total_frames}-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
        "pan_right": f"zoompan=z='1.1':d={total_frames}:x='iw*0.3-iw*0.2*in/{total_frames}-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}",
    }

    zp = zoom_filters.get(direction, zoom_filters["slow_zoom_in"])
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-vf", zp,
        "-t", str(duration), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(VIDEO_CRF),
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def merge_audio_video(video_path, audio_path, output_path):
    """Merge video + audio with apad to prevent truncation.

    FIX B1: No more -shortest truncating voiceover mid-sentence.
    FIX B7: No -pix_fmt with -c:v copy.
    Audio is padded with silence to match video duration exactly.
    """
    video_dur = _probe_duration(video_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        "-af", f"apad=whole_dur={video_dur}",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _ensure_audio_stream(video_path, output_path):
    """Add silent audio track to video-only file at pipeline standard.

    FIX B2/B3: Silent audio matches exact same sample rate and channels
    as voiced segments — no more mono/stereo or 44.1k/48k mismatches.
    """
    video_dur = _probe_duration(video_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_SAMPLE_RATE}:cl=stereo",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        "-t", str(video_dur),
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _has_audio_stream(filepath):
    """Check if a file has an audio stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "a", str(filepath)],
        capture_output=True, text=True
    )
    return "codec_type=audio" in result.stdout


def concat_segments(segment_paths, output_path):
    """Concatenate segments with uniform audio — zero gaps.

    FIX B4: +genpts regenerates timestamps, eliminating AAC priming gaps.
    FIX B6: +faststart enables progressive web playback.

    All segments are first normalized to have identical audio streams
    before concatenation, preventing any codec/rate/channel mismatches.
    """
    if len(segment_paths) <= 1:
        shutil.copy2(str(segment_paths[0]), str(output_path))
        return

    # Normalize: ensure ALL segments have audio at pipeline standard
    normalized = []
    for seg in segment_paths:
        if _has_audio_stream(seg):
            normalized.append(seg)
        else:
            norm_path = seg.parent / f"{seg.stem}_waud{seg.suffix}"
            _ensure_audio_stream(seg, norm_path)
            normalized.append(norm_path)

    concat_file = output_path.parent / f"_concat_{output_path.stem}.txt"
    with open(concat_file, "w") as f:
        for seg in normalized:
            f.write(f"file '{seg}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(VIDEO_CRF),
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        "-pix_fmt", "yuv420p",
        "-fflags", "+genpts",
        "-movflags", "+faststart",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    concat_file.unlink(missing_ok=True)


def _loudnorm_finalize(input_path, output_path):
    """EBU R128 two-pass loudness normalization on final video.

    FIX B5: Ensures consistent volume across all scenes.
    Pass 1: Measure loudness statistics.
    Pass 2: Apply normalization with measured values (linear mode).
    """
    # Pass 1: Measure
    cmd_measure = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd_measure, capture_output=True, text=True)

    # Parse loudnorm JSON from stderr
    stderr = result.stderr
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        # Fallback: single-pass normalization
        cmd_single = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:v", "copy",
            "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
            "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
            "-movflags", "+faststart",
            str(output_path)
        ]
        subprocess.run(cmd_single, check=True, capture_output=True)
        return

    stats = json.loads(stderr[json_start:json_end])

    # Pass 2: Apply with measured values (linear mode = highest quality)
    cmd_apply = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", (
            f"loudnorm=I=-14:TP=-1.5:LRA=11"
            f":measured_I={stats['input_i']}"
            f":measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}"
            f":measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}"
            f":linear=true"
        ),
        "-c:v", "copy",
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", str(AUDIO_CHANNELS),
        "-movflags", "+faststart",
        str(output_path)
    ]
    subprocess.run(cmd_apply, check=True, capture_output=True)


# ══════════════════════════════════════════════════════════════════════
# VISUAL PIPELINE
# ══════════════════════════════════════════════════════════════════════

def _generate_text_frame(scene, output_path):
    """Generate a 1920x1080 PNG text frame using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1920, 1080), color=(20, 20, 25))
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except OSError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Handle text field — can be string or dict {"title": "...", "tag": "..."}
    text_val = scene.get("text")
    if text_val:
        if isinstance(text_val, dict):
            title = text_val.get("title", "")
            tag = text_val.get("tag", "")
            if title:
                bbox = draw.textbbox((0, 0), title, font=font_large)
                tw = bbox[2] - bbox[0]
                draw.text(((1920 - tw) / 2, 420), title, fill="white", font=font_large)
            if tag:
                bbox = draw.textbbox((0, 0), tag, font=font_small)
                tw = bbox[2] - bbox[0]
                draw.text(((1920 - tw) / 2, 520), tag, fill=(180, 180, 190), font=font_small)
        else:
            bbox = draw.textbbox((0, 0), str(text_val), font=font_large)
            tw = bbox[2] - bbox[0]
            draw.text(((1920 - tw) / 2, 420), str(text_val), fill="white", font=font_large)

    if "subtitle" in scene:
        sub = scene["subtitle"]
        bbox = draw.textbbox((0, 0), str(sub), font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((1920 - tw) / 2, 520), str(sub), fill=(180, 180, 190), font=font_small)

    # Handle specs — can be dict or list of dicts
    specs = scene.get("specs")
    if specs:
        y = 300
        if isinstance(specs, dict):
            for key, val in specs.items():
                draw.text((400, y), f"{key}:", fill=(150, 150, 160), font=font_small)
                draw.text((900, y), str(val), fill="white", font=font_small)
                y += 55
        elif isinstance(specs, list):
            for item in specs:
                if isinstance(item, dict):
                    label = item.get("label", item.get("key", ""))
                    value = item.get("value", item.get("val", ""))
                    draw.text((400, y), f"{label}:", fill=(150, 150, 160), font=font_small)
                    draw.text((900, y), str(value), fill="white", font=font_small)
                    y += 55

    if "text_lines" in scene:
        y = 280
        for line in scene["text_lines"]:
            bbox = draw.textbbox((0, 0), line, font=font_large)
            tw = bbox[2] - bbox[0]
            draw.text(((1920 - tw) / 2, y), line, fill="white", font=font_large)
            y += 90

    img.save(str(output_path))


# ══════════════════════════════════════════════════════════════════════
# SCENE RENDERING — voiceover-first approach
# ══════════════════════════════════════════════════════════════════════

def pre_generate_voiceover(narration_text, scene_id, tmp_dir, voice_preset):
    """Generate voiceover BEFORE Ken Burns and return actual duration.

    This is the KEY fix: we must know how long the speech takes BEFORE
    creating the video, so the Ken Burns animation matches exactly.
    Returns (audio_path, vo_duration) or (None, 0) if no narration.
    """
    if not narration_text:
        return None, 0

    audio_path = tmp_dir / f"scene_{scene_id}_vo.aac"
    vo_duration = generate_voiceover(narration_text, audio_path, voice=voice_preset)
    return audio_path, vo_duration


def compute_scene_duration(storyboard_duration, vo_duration, padding=0.5):
    """Compute actual scene duration: max(storyboard, voiceover + padding).

    Ensures narration is NEVER truncated. Padding adds breathing room.
    """
    if vo_duration <= 0:
        return storyboard_duration
    needed = vo_duration + padding
    if needed > storyboard_duration:
        return needed
    return storyboard_duration


def finalize_scene(video_path, audio_path, scene_id, tmp_dir):
    """Merge video + pre-generated voiceover. No truncation possible
    because video was already rendered at the correct duration."""
    if audio_path is None:
        return video_path

    merged_path = tmp_dir / f"scene_{scene_id}_merged.mp4"
    merge_audio_video(video_path, audio_path, merged_path)
    return merged_path


def render_machine_video(storyboard_path):
    """Render a single machine video from storyboard JSON."""
    with open(storyboard_path) as f:
        sb = json.load(f)

    output_path = Path(os.path.expanduser(sb["output"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.parent / f"_tmp_{output_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    render_dir = Path(os.path.expanduser(sb["render_dir"]))
    voice_preset = sb.get("voice_preset", "professional")
    segments = []

    print(f"\n{'='*60}")
    print(f"  Rendering: {sb['title']} ({len(sb['scenes'])} scenes)")
    print(f"{'='*60}")

    for scene in sb["scenes"]:
        raw_id = scene["id"]
        scene_id = raw_id if isinstance(raw_id, str) else str(raw_id)
        scene_type = scene["type"]
        storyboard_dur = scene["duration"]
        narration = scene.get("narration")

        # ── STEP 1: Generate voiceover FIRST to know speech duration ─────
        audio_path, vo_dur = pre_generate_voiceover(narration, scene_id, tmp_dir, voice_preset)
        actual_dur = compute_scene_duration(storyboard_dur, vo_dur)
        if vo_dur > 0 and actual_dur > storyboard_dur:
            print(f"      VO={vo_dur:.1f}s > alloc={storyboard_dur}s -> video={actual_dur:.1f}s")

        # ── STEP 2: Render visuals at the CORRECT duration ───────────────
        if scene_type in ("title_card", "specs_card", "text_overlay"):
            frame_path = tmp_dir / f"scene_{scene_id}_frame.png"
            video_path = tmp_dir / f"scene_{scene_id}.mp4"
            _generate_text_frame(scene, frame_path)
            apply_ken_burns(frame_path, video_path, actual_dur, "slow_zoom_in")
            segments.append(finalize_scene(video_path, audio_path, scene_id, tmp_dir))

        elif scene_type == "3d_model":
            kb_raw = scene.get("ken_burns", "slow_zoom_in")
            kb_direction = kb_raw.get("direction", "slow_zoom_in") if isinstance(kb_raw, dict) else str(kb_raw)
            img_name = scene.get("source_image") or scene.get("image")

            if img_name:
                image_path = render_dir / img_name
                if not image_path.exists():
                    print(f"    WARNING: {image_path.name} not found, skipping")
                    continue
                video_path = tmp_dir / f"scene_{scene_id}_kb.mp4"
                apply_ken_burns(image_path, video_path, actual_dur, kb_direction)

            elif "source_images" in scene:
                orig_splits = scene.get("split", [storyboard_dur // 2, storyboard_dur - storyboard_dur // 2])
                scale = actual_dur / storyboard_dur if storyboard_dur > 0 else 1
                sub_segments = []
                for idx, si_name in enumerate(scene["source_images"]):
                    img_path = render_dir / si_name
                    if not img_path.exists():
                        print(f"    WARNING: {si_name} not found, skipping")
                        continue
                    base_dur = orig_splits[idx] if idx < len(orig_splits) else orig_splits[-1]
                    sub_path = tmp_dir / f"scene_{scene_id}_sub{idx}.mp4"
                    apply_ken_burns(img_path, sub_path, base_dur * scale, kb_direction)
                    sub_segments.append(sub_path)
                if not sub_segments:
                    continue
                video_path = tmp_dir / f"scene_{scene_id}_kb.mp4"
                if len(sub_segments) == 1:
                    shutil.copy2(str(sub_segments[0]), str(video_path))
                else:
                    concat_segments(sub_segments, video_path)
            else:
                continue

            segments.append(finalize_scene(video_path, audio_path, scene_id, tmp_dir))

        elif scene_type == "branding":
            brand_dir = Path(os.path.expanduser(sb.get("brand_dir", str(render_dir))))

            if "source_images" in scene:
                sub_dur = actual_dur / len(scene["source_images"])
                sub_segments = []
                for idx, bimg in enumerate(scene["source_images"]):
                    img_path = brand_dir / bimg
                    if not img_path.exists():
                        img_path = render_dir / bimg
                    if not img_path.exists():
                        placeholder = {"text": bimg}
                        frame_path = tmp_dir / f"scene_{scene_id}_brand{idx}.png"
                        _generate_text_frame(placeholder, frame_path)
                        img_path = frame_path
                    sub_path = tmp_dir / f"scene_{scene_id}_brand{idx}.mp4"
                    kb_raw2 = scene.get("ken_burns", {})
                    kb_d = kb_raw2.get("direction", "slow_zoom_in") if isinstance(kb_raw2, dict) else str(kb_raw2) if kb_raw2 else "slow_zoom_in"
                    apply_ken_burns(img_path, sub_path, sub_dur, kb_d)
                    sub_segments.append(sub_path)
                video_path = tmp_dir / f"scene_{scene_id}_kb.mp4"
                concat_segments(sub_segments, video_path)

            elif "source_image" in scene:
                img_path = brand_dir / scene["source_image"]
                if not img_path.exists():
                    frame_path = tmp_dir / f"scene_{scene_id}_frame.png"
                    _generate_text_frame(scene, frame_path)
                    img_path = frame_path
                video_path = tmp_dir / f"scene_{scene_id}_kb.mp4"
                apply_ken_burns(img_path, video_path, actual_dur, "slow_zoom_in")

            else:
                frame_path = tmp_dir / f"scene_{scene_id}_frame.png"
                _generate_text_frame(scene, frame_path)
                video_path = tmp_dir / f"scene_{scene_id}.mp4"
                apply_ken_burns(frame_path, video_path, actual_dur, "slow_zoom_in")

            segments.append(finalize_scene(video_path, audio_path, scene_id, tmp_dir))

        elif scene_type == "montage":
            img_dur = scene.get("image_duration", 1.5)
            sub_segments = []
            for idx, mimg in enumerate(scene.get("source_images", [])):
                img_path = render_dir / mimg
                if not img_path.exists():
                    continue
                sub_path = tmp_dir / f"scene_{scene_id}_montage{idx}.mp4"
                apply_ken_burns(img_path, sub_path, img_dur, "slow_zoom_in")
                sub_segments.append(sub_path)
            if sub_segments:
                video_path = tmp_dir / f"scene_{scene_id}_montage.mp4"
                concat_segments(sub_segments, video_path)
                segments.append(finalize_scene(video_path, audio_path, scene_id, tmp_dir))

        print(f"    Scene {scene_id}/{len(sb['scenes'])}: {scene_type} ({storyboard_dur}s->{actual_dur:.1f}s) OK")

    # ── Final assembly ────────────────────────────────────────────────
    if not segments:
        print(f"\n  ERROR: No segments produced for {sb['title']}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    # Step 1: Concatenate all scenes
    raw_output = tmp_dir / f"{output_path.stem}_raw.mp4"
    concat_segments(segments, raw_output)

    # Step 2: EBU R128 loudness normalization (two-pass)
    print(f"    Finalizing: EBU R128 loudnorm...")
    _loudnorm_finalize(raw_output, output_path)

    size_mb = output_path.stat().st_size / 1_000_000
    print(f"\n  DONE: {output_path.name} ({size_mb:.1f} MB)")

    # Cleanup tmp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return output_path


# ══════════════════════════════════════════════════════════════════════
# VERIFICATION
# ══════════════════════════════════════════════════════════════════════

def verify_renders():
    """Check all 40 renders exist."""
    views = ["isometric", "isometric_rear", "front", "right", "top"]
    missing = []
    for machine in MACHINES:
        for view in views:
            path = RENDER_DIR / f"{machine}_{view}.png"
            if not path.exists():
                missing.append(str(path))
    return missing


def main():
    parser = argparse.ArgumentParser(description="Render FOFAL machine presentation videos")
    parser.add_argument("--machine", help="Single machine (e.g. cuiseur)")
    parser.add_argument("--global-only", action="store_true", help="Only render global video")
    parser.add_argument("--dry-run", action="store_true", help="Verify renders only")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing = verify_renders()
    if missing:
        print(f"ERROR: {len(missing)} renders missing:")
        for m in missing[:5]:
            print(f"  {m}")
        sys.exit(1)
    print(f"All 40 renders verified in {RENDER_DIR}")

    if args.dry_run:
        print("Dry run complete.")
        return

    t0 = time.time()
    results = []

    if args.global_only:
        sb_path = STORYBOARD_DIR / "global_presentation.json"
        if sb_path.exists():
            results.append(render_machine_video(sb_path))
        else:
            print(f"ERROR: {sb_path} not found"); sys.exit(1)
    elif args.machine:
        matches = [m for m in MACHINES if args.machine in m]
        if not matches:
            print(f"Unknown machine: {args.machine}"); sys.exit(1)
        sb_path = STORYBOARD_DIR / f"{matches[0]}.json"
        if sb_path.exists():
            results.append(render_machine_video(sb_path))
        else:
            print(f"ERROR: {sb_path} not found"); sys.exit(1)
    else:
        for machine in MACHINES:
            sb_path = STORYBOARD_DIR / f"{machine}.json"
            if sb_path.exists():
                results.append(render_machine_video(sb_path))
        global_sb = STORYBOARD_DIR / "global_presentation.json"
        if global_sb.exists():
            results.append(render_machine_video(global_sb))

    elapsed = time.time() - t0
    successful = [r for r in results if r is not None]
    print(f"\n{'='*60}")
    print(f"Pipeline complete: {len(successful)}/{len(results)} videos in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
