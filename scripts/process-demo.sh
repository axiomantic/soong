#!/bin/bash
# Post-process demo video to speed up the waiting section
#
# Usage: ./scripts/process-demo.sh
#
# This script takes the raw VHS output and speeds up:
# 1. Instance boot waiting (wait_start to wait_end) - 8x
# 2. Dead time after boot (wait_end to resume) - 8x
#
# Reads timing info from /tmp/demo-timing.txt (created by demo.tape).

set -e

cd "$(dirname "$0")/.."

RAW_MP4="docs/assets/demo-raw.mp4"
RAW_GIF="docs/assets/demo-raw.gif"
OUT_MP4="docs/assets/demo.mp4"
OUT_GIF="docs/assets/demo.gif"
TIMING_FILE="/tmp/demo-timing.txt"
SPEEDUP=8  # How much faster to play the waiting/dead sections

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
    RESUME_REAL=$(echo "$resume - $start" | bc)

    # Convert to video time (real time / playback speed)
    WAIT_START=$(echo "scale=2; $WAIT_START_REAL / $PLAYBACK_SPEED" | bc)
    WAIT_END=$(echo "scale=2; $WAIT_END_REAL / $PLAYBACK_SPEED" | bc)
    RESUME=$(echo "scale=2; $RESUME_REAL / $PLAYBACK_SPEED" | bc)

    echo "  Timing from recording:"
    echo "    Boot wait:  ${WAIT_START}s - ${WAIT_END}s (video time)"
    echo "    Dead time:  ${WAIT_END}s - ${RESUME}s (video time)"
else
    echo "  Warning: $TIMING_FILE not found, using fallback values"
    WAIT_START=10
    WAIT_END=70
    RESUME=75
fi

# Calculate durations
BOOT_DURATION=$(echo "$WAIT_END - $WAIT_START" | bc)
DEAD_DURATION=$(echo "$RESUME - $WAIT_END" | bc)
BOOT_SPED=$(echo "scale=2; $BOOT_DURATION / $SPEEDUP" | bc)
DEAD_SPED=$(echo "scale=2; $DEAD_DURATION / $SPEEDUP" | bc)

echo "  Boot section: ${BOOT_DURATION}s -> ${BOOT_SPED}s (${SPEEDUP}x)"
echo "  Dead section: ${DEAD_DURATION}s -> ${DEAD_SPED}s (${SPEEDUP}x)"

# Use ffmpeg filter_complex to:
# 1. Split into 4 parts: before, boot wait, dead time, after
# 2. Speed up boot wait and dead time sections
# 3. Concatenate back together

ffmpeg -y -i "$RAW_MP4" -filter_complex "
[0:v]split=4[v1][v2][v3][v4];
[v1]trim=0:${WAIT_START},setpts=PTS-STARTPTS[before];
[v2]trim=${WAIT_START}:${WAIT_END},setpts=(PTS-STARTPTS)/${SPEEDUP}[boot];
[v3]trim=${WAIT_END}:${RESUME},setpts=(PTS-STARTPTS)/${SPEEDUP}[dead];
[v4]trim=${RESUME},setpts=PTS-STARTPTS[after];
[before][boot][dead][after]concat=n=4:v=1:a=0[outv]
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
