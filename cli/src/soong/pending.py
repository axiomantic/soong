"""Pending event queue for Worker sync."""

import json
from pathlib import Path
from typing import List, Tuple

import requests

PENDING_FILE = Path.home() / ".config" / "gpu-dashboard" / "pending.json"


def load_pending_events() -> List[dict]:
    """
    Load pending events from local file.

    Returns:
        List of pending event dictionaries
    """
    if not PENDING_FILE.exists():
        return []

    try:
        with open(PENDING_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_pending_event(event: dict) -> None:
    """
    Add an event to the pending queue.

    Args:
        event: Event dictionary to queue
    """
    pending = load_pending_events()
    pending.append(event)

    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2)


def clear_pending_events() -> None:
    """
    Clear all pending events by removing the pending file.

    Handles gracefully if file doesn't exist.
    """
    PENDING_FILE.unlink(missing_ok=True)


def sync_pending_events(worker_url: str, status_token: str) -> Tuple[int, int]:
    """
    Sync pending events to Worker.

    Args:
        worker_url: Worker base URL
        status_token: STATUS_DAEMON_TOKEN for authentication

    Returns:
        Tuple of (success_count, failure_count)
    """
    pending = load_pending_events()
    if not pending:
        return (0, 0)

    successes = 0
    failures = 0
    remaining = []

    for event in pending:
        try:
            response = requests.post(
                f"{worker_url}/event",
                json=event,
                headers={"Authorization": f"Bearer {status_token}"},
                timeout=(5, 10),
            )
            response.raise_for_status()
            successes += 1
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
            failures += 1
            remaining.append(event)

    # Update pending file with only failed events
    if remaining:
        with open(PENDING_FILE, 'w') as f:
            json.dump(remaining, f, indent=2)
    else:
        PENDING_FILE.unlink(missing_ok=True)

    return (successes, failures)
