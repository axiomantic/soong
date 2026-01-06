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
Set PlaybackSpeed 2
Set WaitTimeout 900s
Set WaitPattern /\$\s*$/

# Activate venv
Hide
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
Type "soong available"
Enter
Wait
Sleep 3s

# Start an instance (this takes several minutes)
Type "soong start -y"
Enter
Wait
Sleep 3s

# Show instance status
Type "soong status"
Enter
Wait
Sleep 3s

# List available models from API
Type "curl -s localhost:8000/v1/models | jq -r '.data[0].id'"
Enter
Wait
Sleep 3s

# Chat with the model
Type `MODEL=$(curl -s localhost:8000/v1/models | jq -r '.data[0].id') && curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+2?\"}]}" | jq -r '.choices[0].message.content'`
Enter
Wait
Sleep 3s

# Show instance status again
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
