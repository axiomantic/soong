# GPU Instance Dashboard

Local FastAPI dashboard for monitoring and managing Lambda GPU instances.

## Features

- Real-time instance monitoring
- Auto-refresh every 30 seconds
- View instance details (uptime, idle time, GPU utilization, model loaded)
- Extend instance leases
- Terminate instances
- Modern dark-themed responsive UI

## Requirements

- Python 3.10+
- Lambda API key configured via `gpu-session configure`
- Status daemon token configured

## Installation

```bash
cd dashboard
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

Dashboard will be available at: http://localhost:8092

## API Endpoints

- `GET /` - Dashboard HTML interface
- `GET /api/instances` - List all instances with status (JSON)
- `POST /api/extend/{instance_id}?hours=2` - Extend instance lease
- `POST /api/terminate/{instance_id}` - Terminate instance
- `GET /health` - Health check

## Configuration

The dashboard reads configuration from `~/.config/gpu-dashboard/config.yaml`:

```yaml
lambda:
  api_key: "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
status_daemon:
  token: "your-status-daemon-token"
```

## UI Features

- **Instance Cards**: Display instance information with status badges
- **GPU Utilization**: Visual progress bar showing GPU usage
- **Model Info**: Shows which model is currently loaded
- **Extend Lease**: Add 2 hours to instance with one click
- **Terminate**: Safely terminate instances via Lambda API
- **Auto-refresh**: Updates every 30 seconds automatically

## Technology Stack

- **Backend**: FastAPI
- **Frontend**: htmx for dynamic updates
- **HTTP Client**: httpx for async API calls
- **Templates**: Jinja2
- **Config**: PyYAML

## Development

To run in development mode with auto-reload:

```bash
uvicorn app:app --reload --port 8092
```

## Notes

- The dashboard communicates with both the Lambda API and instance status daemons
- Instance status daemons must be running and accessible on port 8080
- Firewall rules must allow connections to status daemon ports
- Configuration must be set up via `gpu-session configure` before first use
