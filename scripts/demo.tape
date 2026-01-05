# VHS Demo Script for Soong CLI
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

# Activate venv
Hide
Type "source .venv/bin/activate"
Enter
Sleep 500ms
Show

# Show main help
Type "soong --help"
Sleep 500ms
Enter
Sleep 3s

# List all models with VRAM requirements
Type "soong models"
Sleep 500ms
Enter
Sleep 4s

# Show detailed model info
Type "soong models info deepseek-r1-70b"
Sleep 500ms
Enter
Sleep 4s

# Show available GPUs
Type "soong available"
Sleep 500ms
Enter
Sleep 4s

# Show instance status (with cost tracking)
Type "soong status"
Sleep 500ms
Enter
Sleep 3s

# End
Sleep 2s
