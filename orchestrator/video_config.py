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
    "chapters": "skill_chapters.ChapterGeneration",
    "animation": "skill_animation.AnimationGeneration",
    "cloning": "skill_cloning.VideoCloning",
    "gif": "skill_gif.GifIntegration",
    "broll": "skill_broll.BRollIntegration",
    "audio": "skill_audio.AudioEnhancement",
    "thumbnail": "skill_thumbnail.ThumbnailGeneration",
    "short-form": "skill_shortform.ShortFormExtraction",
    "transitions": "skill_transitions.TransitionsEffects",
    "template": "skill_template.VideoTemplateEngine",
    "script": "skill_script.ScriptGeneration",
    "voiceover": "skill_voiceover.VoiceoverGeneration",
    "color": "skill_color.ColorGrading",
    "brand": "skill_brand.BrandKitManager",
    "multi-format": "skill_multiformat.MultiFormatExport",
    "youtube": "skill_youtube.YouTubePublishing",
}

# Skill execution order (when multiple skills are requested)
SKILL_ORDER = [
    "dead-air",      # 1. Clean up first
    "audio",         # 2. Enhance audio
    "captions",      # 3. Add captions
    "chapters",      # 4. Generate chapters
    "color",         # 5. Apply color grading
    "brand",         # 6. Apply brand kit
    "transitions",   # 7. Add transitions
    "multi-format",  # 8. Export formats
    "thumbnail",     # 9. Generate thumbnail
    "youtube",       # 10. Upload and publish
]

# V-I-V enforcement
VIV_PRINCIPLES = [
    "P1: Verification Autonome - Verify before any action",
    "P2: Pas de Workarounds - No workarounds, permanent solutions only",
    "P3: Cycle V-I-V - Verify-Implement-Verify mandatory",
    "P4: Alignement Holistique - Check all connected systems",
    "P5: Tolerance Zero - Zero tolerance for errors/gaps",
]
