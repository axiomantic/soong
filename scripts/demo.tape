# VHS Demo Script for Soong CLI
# Uses SOONG_MOCK=1 env var to simulate API responses without real GPU costs.
#
# Install vhs: brew install charmbracelet/tap/vhs
# Run: vhs scripts/demo.tape
# Post-process: gifsicle --no-loopcount docs/assets/demo.gif -o docs/assets/demo.gif

Output docs/assets/demo.gif
Output docs/assets/demo.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1000
Set Height 600
Set Theme "Dracula"
Set Padding 20
Set WaitTimeout 120s
Set WaitPattern /[\)$>]\s*$/

# Clean up mock state and set up environment (hidden from recording)
Hide
Type "rm -f /tmp/soong-mock-state.json && source .venv/bin/activate && export SOONG_MOCK=1 && clear"
Enter
Wait
Show

# Show available GPUs
Type "soong available"
Enter
Wait
Sleep 4s

# Start an instance (mock boots in ~5s, then shows panel)
Type "soong start -y"
Enter
Sleep 12s

# Show instance status
Type "soong status"
Enter
Wait
Sleep 4s

# Stop the instance
Type "soong stop -y"
Enter
Sleep 5s

# End
Sleep 2s
