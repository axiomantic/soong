"""Tests for pending.py event queue management."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock
from soong.pending import (
    load_pending_events,
    save_pending_event,
    clear_pending_events,
    sync_pending_events,
    PENDING_FILE,
)


def test_load_pending_events_empty_when_file_not_exists(tmp_path, monkeypatch):
    """Test load_pending_events returns empty list when file doesn't exist."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    events = load_pending_events()

    assert events == []


def test_load_pending_events_reads_from_file(tmp_path, monkeypatch):
    """Test load_pending_events reads events from JSON file."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # Write test events
    test_events = [
        {"event_type": "terminate", "instance_id": "i-123", "timestamp": "2026-01-04T12:00:00Z"},
        {"event_type": "launch", "instance_id": "i-456", "timestamp": "2026-01-04T13:00:00Z"},
    ]
    with open(pending_file, 'w') as f:
        json.dump(test_events, f)

    events = load_pending_events()

    assert events == test_events


def test_save_pending_event_creates_file(tmp_path, monkeypatch):
    """Test save_pending_event creates file and appends event."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    event = {"event_type": "terminate", "instance_id": "i-123", "timestamp": "2026-01-04T12:00:00Z"}

    save_pending_event(event)

    # Verify file was created
    assert pending_file.exists()

    # Verify content
    with open(pending_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0] == event


def test_save_pending_event_appends_to_existing(tmp_path, monkeypatch):
    """Test save_pending_event appends to existing events."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # Create file with existing event
    existing_event = {"event_type": "launch", "instance_id": "i-000", "timestamp": "2026-01-04T11:00:00Z"}
    with open(pending_file, 'w') as f:
        json.dump([existing_event], f)

    # Add new event
    new_event = {"event_type": "terminate", "instance_id": "i-123", "timestamp": "2026-01-04T12:00:00Z"}
    save_pending_event(new_event)

    # Verify both events present
    with open(pending_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0] == existing_event
    assert data[1] == new_event


@patch('soong.pending.requests.post')
def test_sync_pending_events_success_all(mock_post, tmp_path, monkeypatch):
    """Test sync_pending_events successfully syncs all events."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # Create pending events
    events = [
        {"event_type": "terminate", "instance_id": "i-123"},
        {"event_type": "launch", "instance_id": "i-456"},
    ]
    with open(pending_file, 'w') as f:
        json.dump(events, f)

    # Mock successful POST
    mock_post.return_value = Mock(status_code=201)
    mock_post.return_value.raise_for_status = Mock()

    successes, failures = sync_pending_events("https://worker.dev", "token123")

    assert successes == 2
    assert failures == 0
    assert not pending_file.exists()  # File should be deleted


@patch('soong.pending.requests.post')
def test_sync_pending_events_partial_failure(mock_post, tmp_path, monkeypatch):
    """Test sync_pending_events handles partial failures."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    events = [
        {"event_type": "terminate", "instance_id": "i-123"},
        {"event_type": "launch", "instance_id": "i-456"},
    ]
    with open(pending_file, 'w') as f:
        json.dump(events, f)

    # First succeeds, second fails
    import requests
    responses = [
        Mock(status_code=201, raise_for_status=Mock()),
        Mock(status_code=500, raise_for_status=Mock(side_effect=requests.exceptions.HTTPError())),
    ]
    mock_post.side_effect = lambda *args, **kwargs: responses.pop(0)

    successes, failures = sync_pending_events("https://worker.dev", "token123")

    assert successes == 1
    assert failures == 1

    # File should still exist with failed event
    assert pending_file.exists()
    with open(pending_file, 'r') as f:
        remaining = json.load(f)
    assert len(remaining) == 1
    assert remaining[0]["instance_id"] == "i-456"


def test_sync_pending_events_no_events(tmp_path, monkeypatch):
    """Test sync_pending_events returns 0,0 when no events."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    successes, failures = sync_pending_events("https://worker.dev", "token123")

    assert successes == 0
    assert failures == 0


def test_load_pending_events_handles_corrupt_json(tmp_path, monkeypatch):
    """Test load_pending_events returns empty list on corrupt JSON."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # Write corrupt JSON
    with open(pending_file, 'w') as f:
        f.write("{invalid json here")

    events = load_pending_events()

    assert events == []


def test_save_pending_event_creates_directory(tmp_path, monkeypatch):
    """Test save_pending_event creates parent directories if needed."""
    pending_file = tmp_path / "nested" / "dir" / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    event = {"event_type": "launch", "instance_id": "i-789"}

    save_pending_event(event)

    # Verify directory and file were created
    assert pending_file.exists()
    assert pending_file.parent.exists()

    # Verify content
    with open(pending_file, 'r') as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0] == event


@patch('soong.pending.requests.post')
def test_sync_pending_events_handles_connection_error(mock_post, tmp_path, monkeypatch):
    """Test sync_pending_events handles connection errors gracefully."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    events = [{"event_type": "launch", "instance_id": "i-999"}]
    with open(pending_file, 'w') as f:
        json.dump(events, f)

    # Mock connection error
    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError()

    successes, failures = sync_pending_events("https://worker.dev", "token123")

    assert successes == 0
    assert failures == 1

    # File should still exist with failed event
    assert pending_file.exists()
    with open(pending_file, 'r') as f:
        remaining = json.load(f)
    assert len(remaining) == 1
    assert remaining[0]["instance_id"] == "i-999"


@patch('soong.pending.requests.post')
def test_sync_pending_events_handles_timeout(mock_post, tmp_path, monkeypatch):
    """Test sync_pending_events handles timeout errors gracefully."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    events = [{"event_type": "terminate", "instance_id": "i-888"}]
    with open(pending_file, 'w') as f:
        json.dump(events, f)

    # Mock timeout error
    import requests
    mock_post.side_effect = requests.exceptions.Timeout()

    successes, failures = sync_pending_events("https://worker.dev", "token123")

    assert successes == 0
    assert failures == 1

    # File should still exist
    assert pending_file.exists()


def test_clear_pending_events_removes_file(tmp_path, monkeypatch):
    """Test clear_pending_events removes the pending file."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # Create file with events
    events = [{"event_type": "launch", "instance_id": "i-111"}]
    with open(pending_file, 'w') as f:
        json.dump(events, f)

    assert pending_file.exists()

    clear_pending_events()

    assert not pending_file.exists()


def test_clear_pending_events_handles_missing_file(tmp_path, monkeypatch):
    """Test clear_pending_events handles gracefully when file doesn't exist."""
    pending_file = tmp_path / "pending.json"
    monkeypatch.setattr("soong.pending.PENDING_FILE", pending_file)

    # File doesn't exist
    assert not pending_file.exists()

    # Should not raise an error
    clear_pending_events()

    assert not pending_file.exists()
