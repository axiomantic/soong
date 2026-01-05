#!/bin/bash
# Post-process demo video to speed up the waiting section
#
# Usage: ./scripts/process-demo.sh
#
# This script takes the raw VHS output and speeds up the instance boot
# waiting section to keep the demo concise. It reads timing info from
# /tmp/demo-timing.txt (created by demo.tape during recording).

set -e

cd "$(dirname "$0")/.."

RAW_MP4="docs/assets/demo-raw.mp4"
RAW_GIF="docs/assets/demo-raw.gif"
OUT_MP4="docs/assets/demo.mp4"
OUT_GIF="docs/assets/demo.gif"
TIMING_FILE="/tmp/demo-timing.txt"
SPEEDUP=8  # How much faster to play the waiting section

if [ ! -f "$RAW_MP4" ]; then
    echo "Error: $RAW_MP4 not found. Run 'vhs scripts/demo.tape' first."
    exit 1
fi

# Get video duration
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$RAW_MP4")

echo "Processing demo video..."
echo "  Raw video duration: ${VIDEO_DURATION}s"

# Read timing file if it exists
if [ -f "$TIMING_FILE" ]; then
    echo "  Reading timing from $TIMING_FILE"
    source "$TIMING_FILE"

    # Calculate relative timestamps (seconds from start)
    # These are REAL time - need to adjust for PlaybackSpeed 1.5x
    PLAYBACK_SPEED=1.5

    WAIT_START_REAL=$(echo "$wait_start - $start" | bc)
    WAIT_END_REAL=$(echo "$wait_end - $start" | bc)
    TOTAL_REAL=$(echo "$end - $start" | bc)

    # Convert to video time (real time / playback speed)
    WAIT_START=$(echo "scale=2; $WAIT_START_REAL / $PLAYBACK_SPEED" | bc)
    WAIT_END=$(echo "scale=2; $WAIT_END_REAL / $PLAYBACK_SPEED" | bc)

    echo "  Timing from recording:"
    echo "    Real wait: ${WAIT_START_REAL}s - ${WAIT_END_REAL}s"
    echo "    Video wait: ${WAIT_START}s - ${WAIT_END}s (after 1.5x playback)"
else
    echo "  Warning: $TIMING_FILE not found, using fallback values"
    WAIT_START=10
    WAIT_END=70
fi

# Calculate wait duration
WAIT_DURATION=$(echo "$WAIT_END - $WAIT_START" | bc)
SPED_UP_DURATION=$(echo "scale=2; $WAIT_DURATION / $SPEEDUP" | bc)

echo "  Wait section: ${WAIT_DURATION}s -> ${SPED_UP_DURATION}s (${SPEEDUP}x speedup)"

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
echo "Done! Final duration: ${NEW_DURATION%.*}s (was ${VIDEO_DURATION%.*}s)"
