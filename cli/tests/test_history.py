"""Tests for GPU instance termination history tracking.

Following TDD methodology:
1. Write failing tests first (RED)
2. Verify they fail for the right reason
3. Implement minimal code to pass (GREEN)
4. Refactor while keeping tests green

Test coverage:
- HistoryEvent dataclass serialization/deserialization
- HistoryManager local file operations
- HistoryManager time window filtering
- HistoryManager remote API interactions
- HistoryManager sync and fallback behavior
- Error handling for malformed data
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from gpu_session.history import HistoryEvent, HistoryManager


@pytest.fixture
def history_manager_with_temp_dir(tmp_path, monkeypatch):
    """HistoryManager with temporary history file."""
    config_dir = tmp_path / ".config" / "gpu-dashboard"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Patch home directory to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    return HistoryManager()


@pytest.fixture
def sample_history_event():
    """Sample history event for testing."""
    return HistoryEvent(
        timestamp="2025-01-01T12:00:00Z",
        instance_id="i-1234567890abcdef0",
        event_type="termination",
        reason="user_requested",
        uptime_minutes=120,
        gpu_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
    )


@pytest.fixture
def sample_history_events():
    """Multiple sample history events with different timestamps."""
    now = datetime.now(timezone.utc)

    return [
        HistoryEvent(
            timestamp=(now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            instance_id="i-recent1",
            event_type="termination",
            reason="user_requested",
            uptime_minutes=60,
            gpu_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
        ),
        HistoryEvent(
            timestamp=(now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            instance_id="i-recent2",
            event_type="termination",
            reason="lease_expired",
            uptime_minutes=240,
            gpu_type="gpu_1x_a6000",
            region="us-east-1",
        ),
        HistoryEvent(
            timestamp=(now - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            instance_id="i-old1",
            event_type="termination",
            reason="out_of_memory",
            uptime_minutes=30,
            gpu_type="gpu_1x_a10",
            region="us-west-2",
        ),
        HistoryEvent(
            timestamp=(now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            instance_id="i-very-old",
            event_type="termination",
            reason="user_requested",
            uptime_minutes=180,
            gpu_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
        ),
    ]


class TestHistoryEventSerialization:
    """Test HistoryEvent dataclass serialization methods."""

    def test_to_dict_contains_all_fields(self, sample_history_event):
        """to_dict() should return dictionary with all fields."""
        result = sample_history_event.to_dict()

        assert isinstance(result, dict)
        assert result["timestamp"] == "2025-01-01T12:00:00Z"
        assert result["instance_id"] == "i-1234567890abcdef0"
        assert result["event_type"] == "termination"
        assert result["reason"] == "user_requested"
        assert result["uptime_minutes"] == 120
        assert result["gpu_type"] == "gpu_1x_a100_sxm4_80gb"
        assert result["region"] == "us-west-1"

    def test_to_dict_returns_new_dict(self, sample_history_event):
        """to_dict() should return a new dictionary each time."""
        dict1 = sample_history_event.to_dict()
        dict2 = sample_history_event.to_dict()

        assert dict1 == dict2
        assert dict1 is not dict2  # Different objects

    def test_from_dict_creates_event(self):
        """from_dict() should create HistoryEvent from dictionary."""
        data = {
            "timestamp": "2025-01-15T08:30:00Z",
            "instance_id": "i-test123",
            "event_type": "termination",
            "reason": "lease_expired",
            "uptime_minutes": 240,
            "gpu_type": "gpu_1x_a6000",
            "region": "us-east-1",
        }

        event = HistoryEvent.from_dict(data)

        assert isinstance(event, HistoryEvent)
        assert event.timestamp == "2025-01-15T08:30:00Z"
        assert event.instance_id == "i-test123"
        assert event.event_type == "termination"
        assert event.reason == "lease_expired"
        assert event.uptime_minutes == 240
        assert event.gpu_type == "gpu_1x_a6000"
        assert event.region == "us-east-1"

    def test_from_dict_to_dict_roundtrip(self, sample_history_event):
        """Converting to dict and back should preserve all data."""
        original_dict = sample_history_event.to_dict()
        recreated_event = HistoryEvent.from_dict(original_dict)
        final_dict = recreated_event.to_dict()

        assert original_dict == final_dict
        assert recreated_event.timestamp == sample_history_event.timestamp
        assert recreated_event.instance_id == sample_history_event.instance_id
        assert recreated_event.uptime_minutes == sample_history_event.uptime_minutes

    def test_from_dict_missing_field_raises_error(self):
        """from_dict() should raise TypeError when field is missing."""
        incomplete_data = {
            "timestamp": "2025-01-01T12:00:00Z",
            "instance_id": "i-test",
            # Missing required fields
        }

        with pytest.raises(TypeError):
            HistoryEvent.from_dict(incomplete_data)


class TestHistoryManagerInit:
    """Test HistoryManager initialization."""

    def test_init_creates_config_dir(self, tmp_path, monkeypatch):
        """__init__ should create config directory if it doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = HistoryManager()

        expected_dir = tmp_path / ".config" / "gpu-dashboard"
        assert expected_dir.exists()
        assert expected_dir.is_dir()

    def test_init_sets_history_file_path(self, tmp_path, monkeypatch):
        """__init__ should set correct history file path."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manager = HistoryManager()

        expected_file = tmp_path / ".config" / "gpu-dashboard" / "history.json"
        assert manager.history_file == expected_file

    def test_init_does_not_fail_if_dir_exists(self, tmp_path, monkeypatch):
        """__init__ should succeed if config directory already exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".config" / "gpu-dashboard"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise
        manager = HistoryManager()
        assert manager.history_file.parent.exists()


class TestHistoryManagerGetLocalHistory:
    """Test get_local_history() method."""

    def test_get_local_history_empty_when_file_not_exists(self, history_manager_with_temp_dir):
        """get_local_history() should return empty list when file doesn't exist."""
        result = history_manager_with_temp_dir.get_local_history()

        assert result == []
        assert isinstance(result, list)

    def test_get_local_history_loads_all_events(self, history_manager_with_temp_dir, sample_history_events):
        """get_local_history() should load all events from file."""
        # Save events to file
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Load all events (long time window)
        result = history_manager_with_temp_dir.get_local_history(hours=24*365)  # 1 year

        assert len(result) == 4
        assert all(isinstance(event, HistoryEvent) for event in result)

    def test_get_local_history_filters_by_time_window(self, history_manager_with_temp_dir, sample_history_events):
        """get_local_history() should filter events by time window."""
        # Save all events
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Get events from last 24 hours
        result_24h = history_manager_with_temp_dir.get_local_history(hours=24)

        # Should only get events within 24 hours (first two events)
        assert len(result_24h) == 2
        assert result_24h[0].instance_id == "i-recent1"
        assert result_24h[1].instance_id == "i-recent2"

    def test_get_local_history_default_24_hours(self, history_manager_with_temp_dir, sample_history_events):
        """get_local_history() should default to 24 hour window."""
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Call without hours parameter
        result = history_manager_with_temp_dir.get_local_history()

        # Should filter to 24 hours by default
        assert len(result) == 2
        assert all(
            datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            > datetime.now(timezone.utc) - timedelta(hours=24)
            for event in result
        )

    def test_get_local_history_handles_invalid_json(self, history_manager_with_temp_dir):
        """get_local_history() should return empty list for invalid JSON."""
        # Write invalid JSON to file
        history_manager_with_temp_dir.history_file.write_text("{ invalid json }")

        result = history_manager_with_temp_dir.get_local_history()

        assert result == []

    def test_get_local_history_handles_missing_fields(self, history_manager_with_temp_dir):
        """get_local_history() should return empty list when events have missing fields."""
        invalid_data = [
            {
                "timestamp": "2025-01-01T12:00:00Z",
                "instance_id": "i-test",
                # Missing required fields
            }
        ]

        history_manager_with_temp_dir.history_file.write_text(json.dumps(invalid_data))

        result = history_manager_with_temp_dir.get_local_history()

        assert result == []

    def test_get_local_history_handles_invalid_timestamp_format(self, history_manager_with_temp_dir):
        """get_local_history() should return empty list for invalid timestamp."""
        invalid_data = [
            {
                "timestamp": "not-a-timestamp",
                "instance_id": "i-test",
                "event_type": "termination",
                "reason": "test",
                "uptime_minutes": 60,
                "gpu_type": "gpu_1x_a10",
                "region": "us-west-1",
            }
        ]

        history_manager_with_temp_dir.history_file.write_text(json.dumps(invalid_data))

        result = history_manager_with_temp_dir.get_local_history()

        assert result == []

    def test_get_local_history_handles_empty_file(self, history_manager_with_temp_dir):
        """get_local_history() should handle empty JSON file."""
        # Write empty array
        history_manager_with_temp_dir.history_file.write_text("[]")

        result = history_manager_with_temp_dir.get_local_history()

        assert result == []
        assert isinstance(result, list)


class TestHistoryManagerSaveLocalHistory:
    """Test save_local_history() method."""

    def test_save_local_history_creates_file(self, history_manager_with_temp_dir, sample_history_event):
        """save_local_history() should create history file."""
        history_manager_with_temp_dir.save_local_history([sample_history_event])

        assert history_manager_with_temp_dir.history_file.exists()

    def test_save_local_history_writes_valid_json(self, history_manager_with_temp_dir, sample_history_events):
        """save_local_history() should write valid JSON."""
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Should be valid JSON
        content = history_manager_with_temp_dir.history_file.read_text()
        data = json.loads(content)

        assert isinstance(data, list)
        assert len(data) == 4

    def test_save_local_history_preserves_all_fields(self, history_manager_with_temp_dir, sample_history_event):
        """save_local_history() should preserve all event fields."""
        history_manager_with_temp_dir.save_local_history([sample_history_event])

        content = history_manager_with_temp_dir.history_file.read_text()
        data = json.loads(content)

        assert data[0]["timestamp"] == sample_history_event.timestamp
        assert data[0]["instance_id"] == sample_history_event.instance_id
        assert data[0]["event_type"] == sample_history_event.event_type
        assert data[0]["reason"] == sample_history_event.reason
        assert data[0]["uptime_minutes"] == sample_history_event.uptime_minutes
        assert data[0]["gpu_type"] == sample_history_event.gpu_type
        assert data[0]["region"] == sample_history_event.region

    def test_save_local_history_overwrites_existing(self, history_manager_with_temp_dir, sample_history_events):
        """save_local_history() should overwrite existing file."""
        # Save first set
        history_manager_with_temp_dir.save_local_history([sample_history_events[0]])

        # Save second set (should overwrite)
        history_manager_with_temp_dir.save_local_history(sample_history_events[1:])

        result = history_manager_with_temp_dir.get_local_history(hours=24*365)

        # Should only have the second set
        assert len(result) == 3
        assert all(event.instance_id != "i-recent1" for event in result)

    def test_save_local_history_empty_list(self, history_manager_with_temp_dir):
        """save_local_history() should handle empty list."""
        history_manager_with_temp_dir.save_local_history([])

        content = history_manager_with_temp_dir.history_file.read_text()
        data = json.loads(content)

        assert data == []

    def test_save_local_history_formats_with_indent(self, history_manager_with_temp_dir, sample_history_event):
        """save_local_history() should format JSON with indentation."""
        history_manager_with_temp_dir.save_local_history([sample_history_event])

        content = history_manager_with_temp_dir.history_file.read_text()

        # Should have indentation (pretty-printed)
        assert "\n  " in content  # 2-space indent


class TestHistoryManagerFetchRemoteHistory:
    """Test fetch_remote_history() method."""

    def test_fetch_remote_history_success(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """fetch_remote_history() should fetch and parse events from worker."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [event.to_dict() for event in sample_history_events[:2]]
        }
        mock_response.raise_for_status = Mock()

        mock_get = mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.fetch_remote_history(
            "https://worker.example.com", hours=24
        )

        assert result is not None
        assert len(result) == 2
        assert all(isinstance(event, HistoryEvent) for event in result)

        # Verify request was made correctly
        mock_get.assert_called_once_with(
            "https://worker.example.com/history",
            params={"hours": 24},
            timeout=10,
        )

    def test_fetch_remote_history_uses_hours_param(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should pass hours parameter to API."""
        mock_response = Mock()
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = Mock()

        mock_get = mocker.patch("requests.get", return_value=mock_response)

        history_manager_with_temp_dir.fetch_remote_history(
            "https://worker.example.com", hours=48
        )

        call_args = mock_get.call_args
        assert call_args[1]["params"]["hours"] == 48

    def test_fetch_remote_history_default_24_hours(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should default to 24 hours."""
        mock_response = Mock()
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = Mock()

        mock_get = mocker.patch("requests.get", return_value=mock_response)

        history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        call_args = mock_get.call_args
        assert call_args[1]["params"]["hours"] == 24

    def test_fetch_remote_history_network_error(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should return None on network error."""
        import requests
        mocker.patch("requests.get", side_effect=requests.RequestException("Network error"))

        result = history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        assert result is None

    def test_fetch_remote_history_http_error(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should return None on HTTP error."""
        import requests
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        assert result is None

    def test_fetch_remote_history_invalid_json(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should return None for invalid JSON response."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        assert result is None

    def test_fetch_remote_history_missing_events_key(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should return empty list when 'events' key is missing."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}  # Missing 'events'
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        # Uses .get("events", []) so returns empty list, not None
        assert result == []

    def test_fetch_remote_history_malformed_event_data(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should return None for malformed event data."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [
                {
                    "timestamp": "2025-01-01T12:00:00Z",
                    # Missing required fields
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        assert result is None

    def test_fetch_remote_history_timeout(self, history_manager_with_temp_dir, mocker):
        """fetch_remote_history() should use 10 second timeout."""
        mock_response = Mock()
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = Mock()

        mock_get = mocker.patch("requests.get", return_value=mock_response)

        history_manager_with_temp_dir.fetch_remote_history("https://worker.example.com")

        call_args = mock_get.call_args
        assert call_args[1]["timeout"] == 10


class TestHistoryManagerSyncFromWorker:
    """Test sync_from_worker() method."""

    def test_sync_from_worker_success_saves_locally(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """sync_from_worker() should save remote events to local cache on success."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [event.to_dict() for event in sample_history_events[:2]]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com")

        # Should return remote events
        assert len(result) == 2

        # Should save to local cache
        local_events = history_manager_with_temp_dir.get_local_history(hours=24*365)
        assert len(local_events) == 2
        assert local_events[0].instance_id == result[0].instance_id

    def test_sync_from_worker_returns_remote_events(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """sync_from_worker() should return events from worker on success."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [event.to_dict() for event in sample_history_events[:3]]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com", hours=48)

        assert len(result) == 3
        assert all(isinstance(event, HistoryEvent) for event in result)

    def test_sync_from_worker_falls_back_to_local(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """sync_from_worker() should fall back to local cache when remote fetch fails."""
        # Save local events first
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Mock network failure
        import requests
        mocker.patch("requests.get", side_effect=requests.RequestException("Network error"))

        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com", hours=24)

        # Should return local events (first 2 within 24h)
        assert len(result) == 2
        assert result[0].instance_id == "i-recent1"
        assert result[1].instance_id == "i-recent2"

    def test_sync_from_worker_fallback_respects_hours_param(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """sync_from_worker() should pass hours parameter to local fallback."""
        # Save local events
        history_manager_with_temp_dir.save_local_history(sample_history_events)

        # Mock network failure
        import requests
        mocker.patch("requests.get", side_effect=requests.RequestException())

        # Get with longer time window
        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com", hours=48)

        # Should get 3 events (within 48 hours)
        assert len(result) == 3

    def test_sync_from_worker_fallback_empty_when_no_local(self, history_manager_with_temp_dir, mocker):
        """sync_from_worker() should return empty list when both remote and local fail."""
        # Don't save any local events

        # Mock network failure
        import requests
        mocker.patch("requests.get", side_effect=requests.RequestException())

        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com")

        assert result == []

    def test_sync_from_worker_overwrites_old_cache(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """sync_from_worker() should overwrite old local cache with new remote data."""
        # Save old local events
        history_manager_with_temp_dir.save_local_history(sample_history_events[:1])

        # Mock successful remote fetch with different events
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [sample_history_events[2].to_dict()]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        result = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com", hours=48)

        # Should get new remote event
        assert len(result) == 1
        assert result[0].instance_id == "i-old1"

        # Local cache should be updated
        local = history_manager_with_temp_dir.get_local_history(hours=24*365)
        assert len(local) == 1
        assert local[0].instance_id == "i-old1"


class TestHistoryManagerIntegration:
    """Integration tests for full workflows."""

    def test_full_workflow_save_load_sync(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """Test complete workflow: save locally, sync from worker, fallback."""
        # Step 1: Save local events
        history_manager_with_temp_dir.save_local_history(sample_history_events[:2])

        local = history_manager_with_temp_dir.get_local_history(hours=24)
        assert len(local) == 2

        # Step 2: Sync from worker (success)
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [sample_history_events[2].to_dict()]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        synced = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com", hours=48)
        assert len(synced) == 1
        assert synced[0].instance_id == "i-old1"

        # Step 3: Verify cache was updated
        cached = history_manager_with_temp_dir.get_local_history(hours=48)
        assert len(cached) == 1
        assert cached[0].instance_id == "i-old1"

    def test_resilience_to_corrupted_cache(self, history_manager_with_temp_dir, sample_history_events, mocker):
        """Test system handles corrupted cache gracefully."""
        # Corrupt the cache
        history_manager_with_temp_dir.history_file.write_text("{ corrupted json }")

        # Try to load - should get empty
        local = history_manager_with_temp_dir.get_local_history()
        assert local == []

        # Sync from worker should still work
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [sample_history_events[0].to_dict()]
        }
        mock_response.raise_for_status = Mock()

        mocker.patch("requests.get", return_value=mock_response)

        synced = history_manager_with_temp_dir.sync_from_worker("https://worker.example.com")
        assert len(synced) == 1

        # Cache should now be fixed
        local_fixed = history_manager_with_temp_dir.get_local_history()
        assert len(local_fixed) == 1
