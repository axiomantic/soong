# Soong

**Summon GPU instances for AI agent workflows.**

Soong is a CLI tool for managing Lambda Labs GPU instances. Launch, monitor, and connect to GPU instances with a single command.

Named after [Dr. Noonian Soong](https://memory-alpha.fandom.com/wiki/Noonian_Soong), the creator of Data.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- **One-command instance launch** with model and GPU selection
- **SSH tunneling** with automatic port forwarding
- **Cost controls** including lease limits and idle detection
- **Model registry** with VRAM recommendations
- **Rich terminal UI** with progress indicators

## Quick Start

```bash
# Install
cd cli && pip install -e .

# Configure (one-time)
soong configure

# Launch an instance
soong start --model deepseek-r1-70b

# Connect via SSH
soong ssh

# Start tunnel for port forwarding
soong tunnel start

# Check status
soong status

# Stop when done
soong stop
```

## Documentation

Full documentation: [axiomantic.github.io/soong](https://axiomantic.github.io/soong/)

- [Getting Started](https://axiomantic.github.io/soong/getting-started/)
- [User Guides](https://axiomantic.github.io/soong/guides/)
- [CLI Reference](https://axiomantic.github.io/soong/reference/cli-commands/)
- [Architecture](https://axiomantic.github.io/soong/architecture/)

## Requirements

- Python 3.10+
- Lambda Labs account with API key
- SSH key uploaded to Lambda Labs

## Cost Controls

Soong includes multiple layers of cost protection:

1. **Lease system** - Default 4 hours, max 8 hours
2. **Idle detection** - Auto-shutdown after 30 minutes of inactivity
3. **Cost confirmation** - Shows estimated cost before launch
4. **Hard timeout** - 8-hour maximum instance lifetime

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
