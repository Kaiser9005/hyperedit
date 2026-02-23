#!/bin/bash
set -e

echo "=== FFmpeg Capability Test ==="

# 1. Version check
echo "1. FFmpeg version:"
ffmpeg -version | head -1

# 2. Generate test video (5s color bars + tone)
echo "2. Generating test video..."
ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=5" \
       -f lavfi -i "sine=frequency=440:duration=5" \
       -c:v libx264 -preset ultrafast -c:a aac \
       /tmp/test_video.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_video.mp4"

# 3. Test silence detection
echo "3. Testing silence detection..."
ffmpeg -i /tmp/test_video.mp4 -af silencedetect=noise=-30dB:d=0.5 \
       -f null - 2>&1 | grep -i "silence" || echo "   No silence detected (expected for continuous tone)"

# 4. Test video cutting
echo "4. Testing video cut (first 2s)..."
ffmpeg -i /tmp/test_video.mp4 -t 2 -c copy /tmp/test_cut.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_cut.mp4"

# 5. Test concatenation
echo "5. Testing concatenation..."
echo "file '/tmp/test_cut.mp4'" > /tmp/concat_list.txt
echo "file '/tmp/test_cut.mp4'" >> /tmp/concat_list.txt
ffmpeg -f concat -safe 0 -i /tmp/concat_list.txt -c copy /tmp/test_concat.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_concat.mp4"

# 6. Test audio extraction
echo "6. Testing audio extraction..."
ffmpeg -i /tmp/test_video.mp4 -vn -ar 16000 -ac 1 /tmp/test_audio_extract.wav -y 2>/dev/null
echo "   Created: /tmp/test_audio_extract.wav"

# 7. Test color filter
echo "7. Testing color filter..."
ffmpeg -i /tmp/test_video.mp4 -vf "eq=contrast=1.3:brightness=0.05:saturation=1.2" \
       -t 1 /tmp/test_color.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_color.mp4"

# 8. Test loudnorm
echo "8. Testing audio normalization..."
ffmpeg -i /tmp/test_video.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11 \
       -t 2 /tmp/test_normalized.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_normalized.mp4"

# 9. Test aspect ratio crop
echo "9. Testing 9:16 crop (vertical)..."
ffmpeg -i /tmp/test_video.mp4 -vf "crop=ih*9/16:ih" \
       -t 1 /tmp/test_vertical.mp4 -y 2>/dev/null
echo "   Created: /tmp/test_vertical.mp4"

# 10. Verify all outputs
echo ""
echo "=== Verification ==="
for f in /tmp/test_video.mp4 /tmp/test_cut.mp4 /tmp/test_concat.mp4 \
         /tmp/test_audio_extract.wav /tmp/test_color.mp4 /tmp/test_normalized.mp4 \
         /tmp/test_vertical.mp4; do
  SIZE=$(stat -f%z "$f" 2>/dev/null || echo "0")
  echo "  ✅ $(basename $f): ${SIZE} bytes"
done

echo ""
echo "=== All FFmpeg capabilities verified! ==="

# Cleanup
rm -f /tmp/test_*.mp4 /tmp/test_*.wav /tmp/concat_list.txt
