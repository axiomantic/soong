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
Sleep 500ms
Show

# Show help
Type "soong --help"
Enter
Sleep 6s

# Show available models
Type "soong available"
Enter
Sleep 5s

# Start an instance (blocks until ready)
Type "soong start -y"
Enter
Wait+Screen /Instance ready/
Sleep 3s

# Show instance status
Type "soong status"
Enter
Sleep 5s

# List available models
Type "curl -s localhost:8000/v1/models | jq -r '.data[0].id'"
Enter
Sleep 5s

# Chat with the model via OpenAI-compatible API
Type `MODEL=$(curl -s localhost:8000/v1/models | jq -r '.data[0].id') && curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+2?\"}]}" | jq -r '.choices[0].message.content'`
Enter
Sleep 20s

# Show instance status again
Type "soong status"
Enter
Sleep 5s

# Stop the instance (blocks until terminated)
Type "soong stop -y"
Enter
Wait+Screen /terminated/
Sleep 3s

# End
Sleep 2s
