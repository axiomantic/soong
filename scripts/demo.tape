# VHS Demo Script for Soong CLI
# Uses --mock flag to simulate API responses without real GPU costs.
#
# Install vhs: brew install charmbracelet/tap/vhs
# Run: vhs scripts/demo.tape

Output docs/assets/demo.gif
Output docs/assets/demo.mp4

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Dracula"
Set Padding 20
Set PlaybackSpeed 2
Set WaitTimeout 120s
Set WaitPattern /[\)$>]\s*$/

# Clean up mock state and activate venv
Hide
Type "rm -f /tmp/soong-mock-state.json"
Enter
Wait
Type "source .venv/bin/activate"
Enter
Wait
Show

# Show help
Type "soong --help"
Enter
Wait
Sleep 3s

# Show available GPUs
Type "soong --mock available"
Enter
Wait
Sleep 3s

# Start an instance (mock mode - ~5 seconds instead of minutes)
Type "soong --mock start -y --gpu gpu_1x_a100_sxm4_80gb --region us-west-1 --skip-validation"
Enter
Wait
Sleep 3s

# Show instance status
Type "soong --mock status"
Enter
Wait
Sleep 3s

# Stop the instance
Type "soong --mock stop -y"
Enter
Wait
Sleep 3s

# End
Sleep 2s
