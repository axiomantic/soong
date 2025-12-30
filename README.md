# GPU Session CLI

Lambda Labs GPU session management tool.

## Installation

```bash
cd cli
pip install -e .
```

## Quick Start

```bash
# 1. Configure
gpu-session configure

# 2. Launch instance
gpu-session start --model deepseek-r1-70b --hours 4

# 3. Check status
gpu-session status

# 4. SSH into instance
gpu-session ssh

# 5. Stop when done
gpu-session stop
```

## Commands

- `configure` - Set up API keys and defaults
- `start` - Launch new GPU instance
- `status` - Show running instances
- `extend <hours>` - Extend instance lease
- `stop` - Terminate instance
- `ssh` - Connect to instance
- `available` - Show available GPUs
- `tunnel start/stop/status` - Manage SSH tunnels

## Features

- **Retry Logic**: 3 attempts with exponential backoff
- **Rich UI**: Beautiful terminal output
- **Configuration**: YAML-based with secure permissions
- **SSH Tunnels**: Multi-port forwarding
- **Wait Support**: Auto-wait for instance readiness

## Documentation

See `IMPLEMENTATION-SUMMARY.md` for complete details.
