# Lambda GPU Coding Stack

A production-ready system for managing GPU instances on Lambda Labs with intelligent cost controls, persistent storage, and automated service orchestration.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [GPU and Model Options](#gpu-and-model-options)
- [Cost Control](#cost-control)
- [Dashboard](#dashboard)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

Lambda GPU Coding Stack provides a CLI tool and dashboard for launching, managing, and monitoring GPU instances on Lambda Labs. It features automatic service deployment, persistent storage integration, and multi-layered cost controls to prevent runaway costs.

### Key Features

- **One-command GPU instance launch** with automated service deployment
- **Persistent storage** across instance lifecycles via Lambda filesystems
- **Multi-layered cost controls** including idle detection, lease system, and hard timeouts
- **SSH tunnel management** for secure access to remote services
- **Web dashboard** at localhost:8092 for monitoring and control
- **Retry logic** with exponential backoff for API reliability
- **Rich terminal UI** with tables, progress indicators, and color coding

### Use Cases

- Running large language models (DeepSeek-R1 70B, Qwen2.5-Coder 32B)
- GPU-accelerated development environments
- Machine learning experimentation with persistent project storage
- Workflow automation via n8n on GPU instances
- Cost-controlled GPU access with automatic shutdowns

### Tech Stack

- **CLI**: Python 3.x with Typer, Rich, Requests, PyYAML
- **Dashboard**: FastAPI with Jinja2 templates
- **Services**: SGLang (port 8000), n8n (port 5678), Status Daemon (port 8080)
- **Deployment**: Cloud-init with Ansible orchestration
- **Storage**: Lambda persistent filesystems

## Quick Start

### Prerequisites

1. **Lambda Labs account** with billing configured
2. **Lambda API key** from https://cloud.lambdalabs.com/api-keys
3. **SSH key** added to Lambda account at https://cloud.lambdalabs.com/ssh-keys
4. **Lambda filesystem** named `coding-stack` created at https://cloud.lambdalabs.com/file-systems

### Installation

```bash
cd cli
pip install -e .
```

### Configuration

Set up API keys and defaults:

```bash
gpu-session configure
```

You will be prompted for:
- Lambda API key
- Status daemon token (create a secure random string)
- Default region (e.g., `us-west-1`)
- Filesystem name (e.g., `coding-stack`)
- Default model (e.g., `deepseek-r1-70b`)
- Default GPU type (e.g., `gpu_1x_a100_sxm4_80gb`)
- Default lease hours (e.g., `4`)
- SSH key path (e.g., `~/.ssh/id_rsa`)

Configuration is saved to `~/.config/gpu-dashboard/config.yaml` with secure permissions (0600).

### Launch Instance

```bash
gpu-session start --model deepseek-r1-70b
```

The CLI will:
1. Launch an A100 GPU instance in your default region
2. Attach the persistent filesystem
3. Wait for the instance to become active (up to 10 minutes)
4. Display the instance IP and connection commands

### Connect via SSH

```bash
gpu-session ssh
```

### Stop Instance

```bash
gpu-session stop
```

Confirmation is required unless you use the `-y` flag.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Local Machine                             │
│  ┌──────────────────┐              ┌─────────────────────────┐  │
│  │   CLI Tool       │              │  Dashboard :8092        │  │
│  │  gpu-session     │──────────────│  FastAPI Web UI         │  │
│  └──────────────────┘              └─────────────────────────┘  │
│           │                                   │                  │
│           │ Lambda API                        │ Status API       │
│           │                                   │                  │
└───────────┼───────────────────────────────────┼──────────────────┘
            │                                   │
            ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Lambda GPU Instance                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ SGLang       │  │ n8n          │  │ Status Daemon         │ │
│  │ :8000        │  │ :5678        │  │ :8080                 │ │
│  │ Model Server │  │ Workflow     │  │ Health & Lease Mgmt   │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│           │                │                      │              │
└───────────┼────────────────┼──────────────────────┼──────────────┘
            │                │                      │
            ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Persistent Storage Layer                        │
│  /lambda/nfs/coding-stack/                                       │
│  ├── secrets/env.sh          (API keys, tokens)                  │
│  ├── ansible/                (Service deployment configs)        │
│  ├── projects/               (User code and data)                │
│  ├── n8n-data/               (Workflow state)                    │
│  └── venv/                   (Python environments)               │
└─────────────────────────────────────────────────────────────────┘
```

## CLI Reference

| Command | Description | Options |
|---------|-------------|---------|
| `configure` | Set up API keys and defaults | Interactive prompts for all settings |
| `start` | Launch new GPU instance | `--model`, `--gpu`, `--region`, `--hours`, `--name`, `--wait` |
| `status` | Show running instances | `--instance-id` (optional) |
| `extend <hours>` | Extend instance lease | `--instance-id` (optional) |
| `stop` | Terminate instance | `--instance-id` (optional), `-y/--yes` |
| `ssh` | Connect to instance | `--instance-id` (optional) |
| `available` | Show available GPUs and models | None |
| `tunnel start` | Start SSH tunnel | `--sglang-port`, `--n8n-port`, `--status-port` |
| `tunnel stop` | Stop SSH tunnel | None |
| `tunnel status` | Check tunnel status | None |

### Examples

```bash
# Launch instance with custom settings
gpu-session start --model qwen2.5-coder-32b --gpu gpu_1x_rtx6000 --hours 2

# Check status of all instances
gpu-session status

# Extend lease by 2 hours
gpu-session extend 2

# Start tunnel for local access to services
gpu-session tunnel start

# View available GPUs and their availability
gpu-session available
```

## Configuration

### Configuration File

Location: `~/.config/gpu-dashboard/config.yaml`

Permissions: 0600 (read/write for owner only)

### Structure

```yaml
lambda:
  api_key: "your-lambda-api-key"
  default_region: "us-west-1"
  filesystem_name: "coding-stack"

status_daemon:
  token: "your-secure-random-token"
  port: 8080

defaults:
  model: "deepseek-r1-70b"
  gpu: "gpu_1x_a100_sxm4_80gb"
  lease_hours: 4

ssh:
  key_path: "~/.ssh/id_rsa"
```

### Environment Variables

Configuration values can be overridden via command-line options but are not read from environment variables for security reasons.

## GPU and Model Options

### Available GPUs

| GPU Type | VRAM | Cost/hour | Typical Use Cases |
|----------|------|-----------|-------------------|
| `gpu_1x_a100_sxm4_80gb` | 80 GB | ~$1.10 | Large models (70B parameters) |
| `gpu_1x_a100` | 40 GB | ~$1.10 | Medium models (32B parameters) |
| `gpu_1x_rtx6000` | 48 GB | ~$0.50 | Medium models, development |
| `gpu_1x_a10` | 24 GB | ~$0.60 | Small models, fine-tuning |

Pricing varies by region and availability. Check current rates at https://cloud.lambdalabs.com/instances.

### Supported Models

| Model | Parameters | Required GPU | Recommended Use |
|-------|-----------|--------------|-----------------|
| `deepseek-r1-70b` | 70B | A100 80GB | Advanced reasoning, code generation |
| `qwen2.5-coder-32b` | 32B | RTX 6000, A100 | Code completion, development |

Models are loaded via SGLang on port 8000 during instance startup.

## Cost Control

The system implements four layers of cost control to prevent runaway expenses:

### 1. Idle Detection (30 minutes)

The status daemon monitors activity and automatically shuts down the instance after 30 minutes of inactivity.

**Activity signals:**
- HTTP requests to SGLang API
- n8n workflow executions
- SSH connections
- Manual activity updates via API

**Override:** Send activity signal via `/activity` endpoint

### 2. Lease System (4-8 hours)

Instances are launched with a default lease (4 hours). The instance will shut down when the lease expires unless extended.

**Default lease:** 4 hours
**Maximum lease:** 8 hours
**Extension:** Use `gpu-session extend <hours>` or dashboard

### 3. Hard Timeout (8 hours)

Absolute maximum runtime of 8 hours regardless of extensions or activity. The instance will terminate after this period.

**Override:** None (requires relaunching a new instance)

### 4. Cloudflare Watchdog (2 failures)

If deployed behind Cloudflare Workers, the watchdog monitors health checks and terminates the instance after 2 consecutive failures.

**Health check interval:** 5 minutes
**Failure threshold:** 2 consecutive failures
**Endpoint:** `/health`

## Dashboard

**URL:** http://localhost:8092

The dashboard provides a web interface for managing GPU instances.

### Features

- **Instance list** with status, IP, GPU type, region
- **Real-time status** from status daemon (uptime, shutdown time, model info)
- **Lease extension** via web UI
- **Instance termination** with confirmation
- **Health monitoring** showing daemon connectivity

### Usage

1. Start the dashboard:
   ```bash
   cd dashboard
   python app.py
   ```

2. Open browser to http://localhost:8092

3. View all running instances with enhanced status information

### Screenshot Description

The dashboard displays a table of instances showing:
- Instance ID (truncated to 8 characters)
- Instance name
- Status badge (active/pending/terminated)
- IP address
- GPU type
- Region
- Real-time daemon status (uptime, model, shutdown time)
- Action buttons (extend lease, terminate)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Error: Not configured` | Run `gpu-session configure` to set up API keys |
| `No SSH keys found` | Add SSH key at https://cloud.lambdalabs.com/ssh-keys |
| `Filesystem not mounted` | Verify filesystem `coding-stack` exists and is in the correct region |
| `Instance launch timed out` | Check Lambda Labs status page; try different region with `--region` |
| `SSH connection refused` | Wait for instance to complete startup; check `gpu-session status` |
| `Tunnel already running` | Stop existing tunnel with `gpu-session tunnel stop` |
| `API request failed after 3 attempts` | Check API key validity; verify Lambda Labs API is operational |
| `Instance has no IP address` | Instance may still be booting; wait and retry |
| `Status daemon unreachable` | Instance may still be initializing services; check logs via SSH |

### Debug Commands

```bash
# Check instance status
gpu-session status

# SSH into instance to check logs
gpu-session ssh
tail -f /var/log/gpu-stack-boot.log

# Verify services are running
systemctl status sglang
systemctl status n8n
systemctl status status-daemon

# Check persistent storage
ls -la /lambda/nfs/coding-stack
```

## API Reference

### Status Daemon Endpoints

All endpoints require Bearer token authentication.

**Base URL:** `http://<instance-ip>:8080`

**Authentication:** `Authorization: Bearer <status-token>`

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-30T10:00:00Z"
}
```

#### GET /status

Get instance status and lease information.

**Response:**
```json
{
  "status": "running",
  "uptime_seconds": 3600,
  "shutdown_at": "2025-12-30T14:00:00Z",
  "model": "deepseek-r1-70b",
  "last_activity": "2025-12-30T13:00:00Z",
  "lease_hours": 4
}
```

#### POST /extend

Extend instance lease.

**Request Body:**
```
hours=2
```

**Response:**
```json
{
  "extended_by_hours": 2,
  "new_shutdown_at": "2025-12-30T16:00:00Z",
  "total_hours": 6
}
```

**Limits:**
- Maximum total lease: 8 hours
- Returns error if exceeds maximum

#### POST /shutdown

Gracefully shutdown the instance.

**Response:**
```json
{
  "status": "shutting_down",
  "timestamp": "2025-12-30T14:00:00Z"
}
```

#### POST /activity

Signal activity to reset idle timer.

**Response:**
```json
{
  "last_activity": "2025-12-30T14:00:00Z",
  "idle_timeout_at": "2025-12-30T14:30:00Z"
}
```

---

For additional documentation, see:
- [Implementation Summary](IMPLEMENTATION-SUMMARY.md) for technical details
- [Cloud-init Script](cloud-init/user-data.sh) for instance bootstrap process
- [Dashboard README](dashboard/README.md) for dashboard-specific documentation
