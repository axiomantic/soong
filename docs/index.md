# GPU Session CLI

**Effortless GPU instance management for Lambda Labs**

GPU Session is a powerful command-line tool that simplifies managing Lambda Labs GPU instances. Launch, monitor, and connect to GPU instances with a single command—no manual configuration required.

---

## Key Features

### 🚀 **One-Command Instance Management**
Launch GPU instances with your preferred model and instance type in seconds. No need to navigate web consoles or remember complex API calls.

```bash
gpu-session start --model deepseek-ai/DeepSeek-R1 --instance-type gpu_1x_h100_pcie
```

### 🔒 **Automated SSH Tunneling**
Securely access your services through automatically configured SSH tunnels:

- **Port 8000**: SGLang inference server
- **Port 5678**: n8n workflow automation
- **Port 8080**: Instance status daemon

### 💰 **Built-in Cost Controls**
Set maximum runtime limits to prevent unexpected charges. Your instance automatically stops when the time limit is reached.

```bash
gpu-session start --max-hours 2  # Auto-stop after 2 hours
```

### 🤖 **Smart Model Selection**
Browse available models and get instant recommendations for the right GPU instance type based on VRAM requirements.

```bash
gpu-session models --recommend deepseek-ai/DeepSeek-R1
# Recommends: gpu_1x_h100_pcie (80GB VRAM)
```

### 📊 **Real-time Monitoring**
Check instance status, uptime, and cost at any time:

```bash
gpu-session status
# Instance: i-abc123def456 (gpu_1x_h100_pcie)
# Status: running
# Uptime: 1h 23m
# Cost: $2.46
```

---

## Quick Example

```bash
# Configure your Lambda Labs credentials (one-time setup)
gpu-session configure

# Start an instance with DeepSeek-R1
gpu-session start --model deepseek-ai/DeepSeek-R1

# SSH into your instance
gpu-session ssh

# Check status and cost
gpu-session status

# Stop the instance when done
gpu-session stop
```

---

## What's Next?

Ready to get started? Follow our step-by-step guide:

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **[Getting Started](getting-started/index.md)**

    ---

    Set up your Lambda Labs account, install the CLI, and launch your first GPU instance in 5 minutes.

-   :material-cog:{ .lg .middle } **[Configuration Reference](reference/configuration-file.md)**

    ---

    Detailed explanation of all configuration options and advanced settings.

-   :material-console:{ .lg .middle } **[Command Reference](reference/cli-commands.md)**

    ---

    Complete documentation for every CLI command with examples.

-   :material-book-open:{ .lg .middle } **[Architecture](architecture/index.md)**

    ---

    System design, cost controls, and how everything works together.

</div>

---

## Why GPU Session CLI?

Traditional GPU instance management involves:

- Navigating multiple web consoles
- Manually configuring SSH keys and tunnels
- Tracking instance costs in spreadsheets
- Remembering which instance types support which models

**GPU Session CLI eliminates all of this.** Configure once, then launch and manage instances with simple commands. Focus on your work, not infrastructure management.

---

## System Requirements

- **Python**: 3.10 or later
- **Operating System**: Linux, macOS, or Windows (with WSL)
- **Lambda Labs Account**: [Sign up here](https://cloud.lambdalabs.com)

---

## Community & Support

- **GitHub**: [Report issues or contribute](https://github.com/yourusername/gpu-session)
- **Documentation**: You're here!
- **Lambda Labs**: [Official documentation](https://docs.lambdalabs.com)

---

!!! tip "New to Lambda Labs?"
    Check out our [Prerequisites Guide](getting-started/prerequisites.md) for step-by-step instructions on setting up your Lambda Labs account.
