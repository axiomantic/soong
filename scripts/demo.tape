# VHS Demo Script for Soong CLI
# Install vhs: brew install charmbracelet/tap/vhs
#
# Recording flow:
#   1. vhs scripts/demo.tape         # Creates raw recording + timing file
#   2. scripts/process-demo.sh       # Speeds up waiting sections with ffmpeg
#
# Or just: make demo

Output docs/assets/demo-raw.gif
Output docs/assets/demo-raw.mp4

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Dracula"
Set Padding 20
Set PlaybackSpeed 1.5

# Initialize timing file
Hide
Type "source .venv/bin/activate"
Enter
Sleep 500ms
Type "./scripts/demo-timing.sh start"
Enter
Sleep 200ms
Show

# Show help (truncated view of recursive help)
Type "soong --help | head -60"
Sleep 300ms
Enter
Sleep 4s

# Show available GPUs
Type "soong available"
Sleep 300ms
Enter
Sleep 3s

# Record timestamp before instance start
Hide
Type "./scripts/demo-timing.sh wait_start"
Enter
Sleep 100ms
Show

# Start an instance (skip provisioning for faster demo)
Type "soong start -y --skip-provision"
Sleep 300ms
Enter

# Wait for "Instance Ready" or IP address to appear
Wait+Screen /Instance Ready|SGLang API/

# Record timestamp after instance ready
Hide
Type "./scripts/demo-timing.sh wait_end"
Enter
Sleep 100ms
Show

Sleep 2s

# Show status with running instance
Type "soong status"
Sleep 300ms
Enter
Sleep 4s

# Show tunnel status
Type "soong tunnel status"
Sleep 300ms
Enter
Sleep 2s

# Stop the instance
Type "soong stop -y"
Sleep 300ms
Enter
Sleep 3s

# Final status showing no instances
Type "soong status"
Sleep 300ms
Enter
Sleep 2s

# Record end timestamp
Hide
Type "./scripts/demo-timing.sh end"
Enter
Type "./scripts/demo-timing.sh show"
Enter
Sleep 200ms
Show

# End
Sleep 1s
