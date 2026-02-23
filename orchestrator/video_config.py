"""Video editing configuration constants."""

# Timeouts (video processing is slower than code)
TIMEOUT_FFMPEG_ENCODE = 600       # 10 min for encoding
TIMEOUT_WHISPER_TRANSCRIBE = 300  # 5 min for transcription
TIMEOUT_REMOTION_RENDER = 600     # 10 min for animation
TIMEOUT_GEMINI_ANALYZE = 120      # 2 min for AI analysis
TIMEOUT_ELEVENLABS_TTS = 180      # 3 min for voiceover
TIMEOUT_YOUTUBE_UPLOAD = 600      # 10 min for upload

# Video defaults
DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_FPS = 30
DEFAULT_CODEC = "libx264"
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_BITRATE = "192k"
TARGET_LUFS = -14
TARGET_TP = -1.5

# Skill labels (Linear issue labels -> skill mapping)
SKILL_LABELS = {
    "dead-air": "skill_dead_air.DeadAirRemoval",
    "captions": "skill_captions.CaptionGeneration",
    "chapters": "skill_chapters.ChapterGenerator",
    "animation": "skill_animation.AnimationOverlay",
    "style": "skill_style.StyleTransfer",
    "gif": "skill_gif.GifManager",
    "broll": "skill_broll.BRollInserter",
    "audio": "skill_audio.AudioEnhancement",
    "thumbnail": "skill_thumbnail.ThumbnailGenerator",
    "short-form": "skill_shortform.ShortFormExtractor",
    "transitions": "skill_transitions.TransitionManager",
    "template": "skill_template.TemplateEngine",
    "script": "skill_script.ScriptGenerator",
    "voiceover": "skill_voiceover.VoiceoverGenerator",
    "color": "skill_color.ColorGrading",
    "brand": "skill_brand.BrandKitManager",
    "export": "skill_export.MultiFormatExporter",
    "youtube": "skill_youtube.YouTubePublisher",
}

# Skill execution order (when multiple skills are requested)
# Pipeline skills first (video-in/video-out), then generation/export/publish.
SKILL_ORDER = [
    "dead-air",      # 1. Clean up silence/dead air
    "audio",         # 2. Enhance audio quality
    "style",         # 3. Apply style transfer
    "color",         # 4. Color grading
    "brand",         # 5. Apply brand kit (watermark/overlay)
    "animation",     # 6. Animation overlays
    "broll",         # 7. Insert B-roll footage
    "transitions",   # 8. Add transitions between clips
    "captions",      # 9. Generate/burn captions
    "chapters",      # 10. Generate chapters
    "script",        # 11. Generate script/storyboard
    "voiceover",     # 12. Generate voiceover audio
    "template",      # 13. Apply video template
    "gif",           # 14. Extract GIF previews
    "short-form",    # 15. Extract short-form clips
    "thumbnail",     # 16. Generate thumbnails
    "export",        # 17. Multi-format export
    "youtube",       # 18. Upload and publish
]

# V-I-V enforcement
VIV_PRINCIPLES = [
    "P1: Verification Autonome - Verify before any action",
    "P2: Pas de Workarounds - No workarounds, permanent solutions only",
    "P3: Cycle V-I-V - Verify-Implement-Verify mandatory",
    "P4: Alignement Holistique - Check all connected systems",
    "P5: Tolerance Zero - Zero tolerance for errors/gaps",
]
