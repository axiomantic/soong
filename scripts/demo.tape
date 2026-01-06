# VHS Demo Script for Soong CLI
# Uses SOONG_MOCK=1 env var to simulate API responses without real GPU costs.
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

# Clean up mock state and set up environment
Hide
Type "rm -f /tmp/soong-mock-state.json"
Enter
Wait
Type "source .venv/bin/activate"
Enter
Wait
Type "export SOONG_MOCK=1"
Enter
Wait
Show

# Show help
Type "soong --help"
Enter
Wait
Sleep 3s

# Show available GPUs
Type "soong available"
Enter
Wait
Sleep 3s

# Start an instance
Type "soong start -y"
Enter
Wait
Sleep 3s

# Show instance status
Type "soong status"
Enter
Wait
Sleep 3s

# Stop the instance
Type "soong stop -y"
Enter
Wait
Sleep 3s

# End
Sleep 2s
