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

# Activate venv
Hide
Type "source .venv/bin/activate"
Enter
Sleep 500ms
Show

# Show help
Type "soong --help"
Sleep 300ms
Enter
Sleep 4s

# Show available models
Type "soong available"
Sleep 300ms
Enter
Sleep 3s

# Start an instance
Type "soong start -y"
Sleep 300ms
Enter

# Wait for instance to be ready (boot + provision + health check)
Sleep 600s

Sleep 2s

# Show instance status
Type "soong status"
Sleep 300ms
Enter
Sleep 3s

# Chat with the model via OpenAI-compatible API
Type `curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"default","messages":[{"role":"user","content":"What is 2+2?"}]}' | jq .choices[0].message.content`
Sleep 300ms
Enter
Sleep 5s

# Stop the instance
Type "soong stop -y"
Sleep 300ms
Enter
Sleep 3s

# Show no instances running
Type "soong status"
Sleep 300ms
Enter
Sleep 2s

# End
Sleep 1s
