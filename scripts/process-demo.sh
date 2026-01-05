#!/bin/bash
# Post-process demo video to speed up the waiting section
#
# Usage: ./scripts/process-demo.sh
#
# This script takes the raw VHS output and speeds up the instance boot
# waiting section to keep the demo concise.

set -e

cd "$(dirname "$0")/.."

RAW_MP4="docs/assets/demo-raw.mp4"
RAW_GIF="docs/assets/demo-raw.gif"
OUT_MP4="docs/assets/demo.mp4"
OUT_GIF="docs/assets/demo.gif"

# Timing (in seconds) - adjust these based on actual recording
# These are timestamps in the RAW video (after 1.5x playback speed)
WAIT_START=10      # When "soong start" command begins
WAIT_END=70        # When instance is ready and next command starts
SPEEDUP=8          # How much faster to play the waiting section (8x)

if [ ! -f "$RAW_MP4" ]; then
    echo "Error: $RAW_MP4 not found. Run 'vhs scripts/demo.tape' first."
    exit 1
fi

echo "Processing demo video..."
echo "  Wait section: ${WAIT_START}s - ${WAIT_END}s (speeding up ${SPEEDUP}x)"

# Get video duration
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$RAW_MP4")
DURATION=${DURATION%.*}  # Remove decimals

echo "  Total duration: ${DURATION}s"

# Calculate new duration of sped-up section
WAIT_DURATION=$((WAIT_END - WAIT_START))
SPED_UP_DURATION=$(echo "scale=2; $WAIT_DURATION / $SPEEDUP" | bc)

echo "  Wait section: ${WAIT_DURATION}s -> ${SPED_UP_DURATION}s"

# Use ffmpeg filter_complex to:
# 1. Split into 3 parts: before wait, wait, after wait
# 2. Speed up the wait section
# 3. Concatenate back together

ffmpeg -y -i "$RAW_MP4" -filter_complex "
[0:v]split=3[v1][v2][v3];
[v1]trim=0:${WAIT_START},setpts=PTS-STARTPTS[before];
[v2]trim=${WAIT_START}:${WAIT_END},setpts=(PTS-STARTPTS)/${SPEEDUP}[wait];
[v3]trim=${WAIT_END},setpts=PTS-STARTPTS[after];
[before][wait][after]concat=n=3:v=1:a=0[outv]
" -map "[outv]" -c:v libx264 -preset slow -crf 22 "$OUT_MP4"

echo "Created $OUT_MP4"

# Also create GIF from the processed MP4
echo "Creating GIF..."
ffmpeg -y -i "$OUT_MP4" \
    -vf "fps=10,scale=1200:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
    -loop 0 \
    "$OUT_GIF"

echo "Created $OUT_GIF"

# Show final duration
NEW_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUT_MP4")
echo ""
echo "Done! Final duration: ${NEW_DURATION%.*}s (was ${DURATION}s)"
