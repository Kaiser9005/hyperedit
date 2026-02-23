---
name: voiceover-generation
description: Generate voiceover audio from text using ElevenLabs API and merge with video
---

# Voiceover Generation

## When to Use
When user asks to add narration, voiceover, text-to-speech, or spoken commentary to a video.

## Process (V-I-V)
### VERIFY: Text not empty, voice preset exists, video path valid (if merging)
### IMPLEMENT: Generate speech audio via ElevenLabs TTS -> optionally merge with video via FFmpegService.merge_audio()
### VERIFY: Output audio/video file exists, duration matches expected speech length

## Parameters
- `text`: The script/text to convert to speech (required)
- `voice`: Voice preset name from VOICES dict (default: "narrator_male")
- `video_path`: Optional video file to merge voiceover into
- `merge_with_video`: Whether to merge generated audio with video (default: true)
- `output_path`: Path for the output audio or video file

## Voice Presets
- `narrator_male`: Adam - narrative style
- `narrator_female`: Sarah - narrative style
- `professional`: Daniel - professional style
- `friendly`: Emily - friendly style
- `energetic`: Sam - energetic style

## Notes
- ElevenLabs API key required via ELEVENLABS_API_KEY env var
- Falls back to silent placeholder audio when API key is not set (for testing)
- Speech duration estimated at ~150 words per minute (2.5 words/sec)
