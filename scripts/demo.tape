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

# Activate venv
Hide
Type "source .venv/bin/activate"
Enter
Sleep 1s
Show

# Show help (wait for prompt after)
Type "soong --help"
Enter
Wait+Screen /worker/
Sleep 3s

# Clear and show available GPUs
Ctrl+L
Sleep 500ms
Type "soong available"
Enter
Wait+Screen /Price/
Sleep 3s

# Clear and start an instance
Ctrl+L
Sleep 500ms
Type "soong start -y"
Enter
Wait+Screen /Instance ready/
Sleep 3s

# Show instance status
Ctrl+L
Sleep 500ms
Type "soong status"
Enter
Wait+Screen /active/
Sleep 3s

# List available models from API
Ctrl+L
Sleep 500ms
Type "curl -s localhost:8000/v1/models | jq -r '.data[0].id'"
Enter
Sleep 5s

# Chat with the model
Ctrl+L
Sleep 500ms
Type `MODEL=$(curl -s localhost:8000/v1/models | jq -r '.data[0].id') && curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+2?\"}]}" | jq -r '.choices[0].message.content'`
Enter
Sleep 20s

# Show instance status again
Ctrl+L
Sleep 500ms
Type "soong status"
Enter
Wait+Screen /active/
Sleep 3s

# Stop the instance
Ctrl+L
Sleep 500ms
Type "soong stop -y"
Enter
Wait+Screen /terminated/
Sleep 3s

# End
Sleep 2s
