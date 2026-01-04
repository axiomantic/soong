# Soong - GPU Instance Management CLI

## Overview

Soong is a CLI tool for managing Lambda Labs GPU instances with automatic cost controls and idle detection. It provides one-command instance launching, real-time status monitoring, automatic shutdown of idle instances, and SSH tunnel management.

**Key value**: Multi-layer cost protection prevents runaway expenses from forgotten GPU instances ($0.50-$2.00/hour).

## Architecture

```
Local Machine (User)
  └─ CLI Tool (Python/Typer/Rich) → Lambda Labs API
                                  ↓
GPU Instance (Lambda Labs)
  ├─ Status Daemon (Flask :8080) ← lifecycle/idle management
  ├─ SGLang Server (:8000) - LLM inference
  ├─ n8n Workflows (:5678) - automation
  └─ Persistent Filesystem (/lambda/nfs/coding-stack/)

Cloudflare Worker (Optional)
  └─ Watchdog Monitor (health checks every 5 min)
```

## Key Directories

| Path | Purpose |
|------|---------|
| `cli/src/soong/` | Main CLI application code |
| `cli/src/soong/cli.py` | Entry point, all commands |
| `cli/src/soong/lambda_api.py` | Lambda Labs API client |
| `cli/src/soong/instance.py` | Instance lifecycle management |
| `cli/src/soong/config.py` | Configuration schema/validation |
| `cli/src/soong/models.py` | AI model registry, GPU recommendations |
| `cli/src/soong/ssh.py` | SSH tunnel management |
| `ansible/` | Instance provisioning playbooks |
| `ansible/roles/status-daemon/templates/status_daemon.py.j2` | **Status daemon (server component)** |
| `worker/` | Cloudflare Worker watchdog |
| `docs/architecture/` | System design documentation |

## Glossary

| Term | Definition |
|------|------------|
| **Lease Duration** | Time commitment in hours (1-8) when launching an instance |
| **IDLE_TIMEOUT_MINUTES** | Minutes without activity before auto-shutdown (default: 30) |
| **LAST_ACTIVITY** | Timestamp of last detected activity (SSH, manual signal) |
| **Status Token** | Shared secret for authenticating daemon endpoints (32-byte URL-safe) |
| **Hard Timeout** | Absolute 8-hour limit from creation, no overrides |
| **Watchdog** | Cloudflare Worker that monitors health externally |
| **SGLang** | LLM inference server running on the GPU instance |
| **n8n** | Workflow automation platform running on the instance |

## Cost Control Layers

1. **Layer 1: Idle Detection (30 min)** - No activity → auto-shutdown
2. **Layer 2: Lease System (4hr default, max 8hr)** - Hard deadline
3. **Layer 3: Hard Timeout (8hr absolute)** - No exceptions
4. **Layer 4: Cloudflare Watchdog** - External failsafe

## Status Daemon (Server Component)

**Location**: `ansible/roles/status-daemon/templates/status_daemon.py.j2`

Flask server running on GPU instances at port 8080.

### Endpoints

| Endpoint | Method | Auth | Purpose | Updates LAST_ACTIVITY? |
|----------|--------|------|---------|------------------------|
| `/health` | GET | No | Health check | No |
| `/status` | GET | Yes | Instance status JSON | No |
| `/activity` | POST | Yes | Signal activity manually | **Yes** |
| `/extend` | POST | Yes | Extend lease deadline | No |
| `/shutdown` | POST | Yes | Admin termination | No |
| `/` | GET | Yes | HTML dashboard | No |

### Background Thread: `idle_checker()`

Runs every 60 seconds, checks:
1. Active connections to SGLang API (port 8000) → reset LAST_ACTIVITY
2. Lease expired → terminate
3. Idle > 30 min → terminate

### Activity Detection

Activity resets LAST_ACTIVITY when:
- Active TCP connections to SGLang API (port 8000) detected via `ss`
- Manual POST to `/activity` endpoint

The idle checker runs every 60 seconds and checks for established connections to the SGLang port. If clients are connected, the idle timer resets.

## CLI Commands

```bash
soong configure    # Interactive setup wizard
soong start        # Launch GPU instance
soong status       # Show instance status and costs
soong ssh          # Interactive SSH session
soong tunnel       # Start SSH tunnels to services
soong extend <hrs> # Extend lease duration
soong stop         # Terminate instance
```

## Configuration

Located at `~/.config/gpu-dashboard/config.yaml`:

```yaml
lambda:
  api_key: string          # Lambda API key
  default_region: string   # e.g., "us-west-1"
  filesystem_name: string  # e.g., "coding-stack"

status_daemon:
  token: string            # Shared secret
  port: int                # Default: 8080

defaults:
  model: string            # Default model ID
  gpu: string              # Default GPU type
  lease_hours: int         # Default: 4
```

## Development Setup

```bash
cd cli
pip install -e ".[test]"
soong configure
```

## Testing

```bash
cd cli
pytest                    # Run all tests
pytest -v                 # Verbose
pytest tests/test_cli.py  # Specific file
```

## Instance Provisioning Flow

1. CLI calls Lambda API to launch instance
2. Cloud-init runs on instance boot
3. Ansible provisions services (SGLang, n8n, status-daemon)
4. Status daemon starts background idle_checker thread
5. Instance signals ready via health endpoint

## Jinja2 Template Variables (Status Daemon)

The status daemon template uses these Ansible variables:
- `{{ lambda_api_key }}` - API key for termination calls
- `{{ status_token }}` - Bearer token for auth
- `{{ idle_timeout_minutes }}` - Idle threshold (default: 30)
- `{{ lease_hours }}` - Initial lease duration
- `{{ max_lease_hours }}` - Maximum lease (default: 8)
- `{{ sglang_port }}` - SGLang API port (default: 8000)
- `{{ status_daemon_port }}` - Daemon port (default: 8080)
