"""History tracking for GPU instance terminations."""

import json
import requests
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone


@dataclass
class HistoryEvent:
    """Represents a history event (instance termination)."""
    timestamp: str
    instance_id: str
    event_type: str
    reason: str
    uptime_minutes: int
    gpu_type: str
    region: str

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEvent":
        """Create from dictionary."""
        return cls(**data)


class HistoryManager:
    """Manager for instance termination history."""

    def __init__(self):
        """Initialize history manager with local cache file."""
        config_dir = Path.home() / ".config" / "gpu-dashboard"
        config_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = config_dir / "history.json"

    def get_local_history(self, hours: int = 24) -> List[HistoryEvent]:
        """
        Load history from local cache.

        Args:
            hours: Number of hours to look back

        Returns:
            List of history events within the time window
        """
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)

            events = [HistoryEvent.from_dict(event) for event in data]

            # Filter by time window
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            filtered = [
                event for event in events
                if datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')) > cutoff
            ]

            return filtered
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return []

    def save_local_history(self, events: List[HistoryEvent]):
        """
        Save history to local cache.

        Args:
            events: List of history events to save
        """
        with open(self.history_file, 'w') as f:
            json.dump([event.to_dict() for event in events], f, indent=2)

    def fetch_remote_history(
        self, worker_url: str, hours: int = 24
    ) -> Optional[List[HistoryEvent]]:
        """
        Fetch history from Cloudflare Worker.

        Args:
            worker_url: Base URL of the Cloudflare Worker
            hours: Number of hours to look back

        Returns:
            List of history events or None if fetch failed
        """
        try:
            response = requests.get(
                f"{worker_url}/history",
                params={"hours": hours},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            return [HistoryEvent.from_dict(event) for event in data.get("events", [])]
        except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError):
            return None

    def sync_from_worker(
        self, worker_url: str, hours: int = 24
    ) -> List[HistoryEvent]:
        """
        Sync history from worker and cache locally.

        Args:
            worker_url: Base URL of the Cloudflare Worker
            hours: Number of hours to look back

        Returns:
            List of history events (from worker if available, otherwise local cache)
        """
        # Try to fetch from worker
        remote_events = self.fetch_remote_history(worker_url, hours)

        if remote_events is not None:
            # Save to local cache
            self.save_local_history(remote_events)
            return remote_events

        # Fall back to local cache
        return self.get_local_history(hours)
