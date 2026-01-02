# Architecture Documentation

This section provides technical documentation of the soong CLI system architecture, design decisions, and implementation details.

## Contents

- [System Design](system-design.md) - Overall architecture and component interactions
- [Cost Controls](cost-controls.md) - Multi-layered cost protection mechanisms

## Overview

The soong CLI is a production-ready system for managing GPU instances on Lambda Labs. It provides a robust CLI interface backed by a distributed architecture that emphasizes:

- **Reliability**: Retry logic with exponential backoff for API calls
- **Cost Control**: Multiple layers of protection against runaway costs
- **Persistence**: Integration with Lambda filesystems for state across sessions
- **Security**: Token-based authentication, secure configuration storage
- **User Experience**: Rich terminal UI with progress indicators and detailed status

## Key Components

1. **CLI Tool** (`soong`) - Python-based command-line interface
2. **Lambda API Client** - HTTP client with retry logic and error handling
3. **SSH Tunnel Manager** - Manages port forwarding for remote services
4. **Instance Manager** - Lifecycle management and status polling
5. **Status Daemon** (on GPU instance) - Health monitoring and lease management
6. **Configuration Manager** - YAML-based configuration with validation

## Design Principles

### Fail-Safe Defaults

All default settings prioritize safety and cost control:

- Default lease: 4 hours (not maximum)
- Idle timeout: 30 minutes
- Hard timeout: 8 hours (absolute maximum)
- Cost estimates shown before launch
- Confirmation required for destructive operations

### Single Source of Truth

Configuration is centralized in `~/.config/gpu-dashboard/config.yaml` with secure permissions (0600). Command-line flags override defaults but do not modify saved configuration.

### Graceful Degradation

The system continues to function when optional services are unavailable:

- Cost estimates work without pricing API
- Status shows partial info when daemon unreachable
- History shows local cache when worker unavailable

### Progressive Disclosure

The CLI presents information hierarchically:

1. Critical information first (instance ID, status, IP)
2. Cost and timing details for active instances
3. Extended details via flags (`--history`, `--stopped`)
4. Debug information via SSH and logs

## Next Steps

- [System Design](system-design.md) - Detailed architecture diagrams
- [Cost Controls](cost-controls.md) - Cost protection mechanisms
