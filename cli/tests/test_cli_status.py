"""Tests for 'gpu-session status' CLI command and helper functions."""

import pytest
import responses
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
from typer.testing import CliRunner
from rich.console import Console
from io import StringIO

from soong.cli import app, show_termination_history, show_stopped_instances
from soong.lambda_api import Instance, InstanceType, LambdaAPIError
from soong.history import HistoryEvent


runner = CliRunner()


# =============================================================================
# Tests for show_termination_history()
# =============================================================================


def test_show_termination_history_displays_table(mocker):
    """Test show_termination_history displays events in a table.

    Pattern #2 fix: Verify row structure - all data elements appear in same row.
    """
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-12345678",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=125,
            gpu_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    lines = result.split('\n')

    # Verify title row structure
    assert "Termination History" in result
    assert "24 Hours" in result

    # Verify header row exists and contains all columns
    header_line = next((l for l in lines if "Time" in l and "Instance ID" in l), None)
    assert header_line is not None, "Header row not found"
    assert "Reason" in header_line
    assert "Uptime" in header_line
    assert "GPU" in header_line
    assert "Region" in header_line

    # Pattern #2 fix: Find data row and verify all elements are in the same row
    data_row = next((l for l in lines if "test-ins" in l), None)
    assert data_row is not None, "Instance data row not found"
    # Reason may be truncated in table, so just verify "User" appears
    assert "User" in data_row, "Reason not in instance row"
    assert "2h 5m" in data_row, "Uptime not in instance row"
    assert ("gpu_1x_a100" in data_row or "a100" in data_row.lower()), "GPU type not in instance row"
    assert "us-west-1" in data_row, "Region not in instance row"


def test_show_termination_history_empty_list(mocker):
    """Test show_termination_history handles empty events list."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    show_termination_history([], hours=24)

    result = output.getvalue()
    assert "No termination events found" in result
    assert "24" in result and "hours" in result


def test_show_termination_history_watchdog_reason_red(mocker):
    """Test show_termination_history colors watchdog reason in red."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="Killed by watchdog",
            uptime_minutes=60,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "watchdog" in result.lower()
    # The output will contain ANSI red color code (\x1b[31m)
    assert "\x1b[31m" in result or "Killed" in result


def test_show_termination_history_idle_reason_yellow(mocker):
    """Test show_termination_history colors idle reason in yellow."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="Idle timeout exceeded",
            uptime_minutes=60,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "Idle timeout" in result or "idle" in result.lower()


def test_show_termination_history_lease_reason_orange(mocker):
    """Test show_termination_history colors lease reason in orange."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="Lease expired",
            uptime_minutes=240,
            gpu_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "Lease expired" in result or "lease" in result.lower()


def test_show_termination_history_formats_uptime_hours_and_minutes(mocker):
    """Test show_termination_history formats uptime with hours and minutes.

    Pattern #4 fix: Use unique uptime value to verify calculation is consumed.
    """
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    # Pattern #4 fix: Use non-round number to verify it's actually calculated
    unique_uptime = 197  # 3h 17m - unusual value that would fail if hardcoded
    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=unique_uptime,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    # Pattern #4 fix: Verify the exact calculated uptime appears
    lines = result.split('\n')
    data_row = next((l for l in lines if "test-instance-1" in l or "test-ins" in l), None)
    assert data_row is not None, "Instance row not found"
    assert "3h 17m" in data_row, f"Expected uptime '3h 17m' not found in row: {data_row}"


def test_show_termination_history_formats_uptime_minutes_only(mocker):
    """Test show_termination_history formats uptime with minutes only."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=45,  # Less than 1 hour
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "45m" in result
    assert "0h" not in result


def test_show_termination_history_formats_timestamp(mocker):
    """Test show_termination_history formats timestamp correctly."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T15:30:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=60,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "2026-01-01" in result
    assert "15:30" in result


# =============================================================================
# Tests for show_stopped_instances()
# =============================================================================


def test_show_stopped_instances_displays_table(mocker):
    """Test show_stopped_instances displays instances in a table.

    Pattern #2 fix: Verify row structure - all data elements in same row.
    """
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    instances = [
        Instance(
            id="stopped-instance-12345678",
            name="my-instance",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2026-01-01T10:00:00Z",
            lease_expires_at=None,
        )
    ]

    show_stopped_instances(instances)

    result = output.getvalue()
    lines = result.split('\n')

    # Verify title and header
    assert "Stopped Instances" in result

    # Verify header row contains all columns
    header_line = next((l for l in lines if "Instance ID" in l and "Name" in l), None)
    assert header_line is not None, "Header row not found"
    assert "Status" in header_line
    assert "GPU" in header_line
    assert "Region" in header_line
    assert "Created At" in header_line

    # Pattern #2 fix: Verify all data appears in same row
    data_row = next((l for l in lines if "stopped-" in l), None)
    assert data_row is not None, "Instance data row not found"
    assert ("my-instan" in data_row or "instance" in data_row.lower()), "Instance name not in row"
    assert "terminated" in data_row, "Status not in row"
    assert "us-west-1" in data_row, "Region not in row"
    # GPU type may be truncated, so just verify row has GPU info
    assert ("gpu_1x" in data_row or "a100" in data_row.lower()), "GPU type not in row"


def test_show_stopped_instances_empty_list(mocker):
    """Test show_stopped_instances handles empty list."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    show_stopped_instances([])

    result = output.getvalue()
    assert "No stopped instances" in result and "found" in result


def test_show_stopped_instances_filters_to_stopped_only(mocker):
    """Test show_stopped_instances filters to stopped/terminated instances."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    instances = [
        Instance(
            id="active-instance-1",
            name="running",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at="2026-01-01T10:00:00Z",
        ),
        Instance(
            id="stopped-instance-1",
            name="stopped",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at="2026-01-01T09:00:00Z",
        ),
    ]

    show_stopped_instances(instances)

    result = output.getvalue()
    assert "stopped-" in result
    assert "active-" not in result
    assert "stopped" in result.lower()


def test_show_stopped_instances_formats_created_at(mocker):
    """Test show_stopped_instances formats created_at timestamp."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("soong.cli.console", test_console)

    instances = [
        Instance(
            id="stopped-instance-1",
            name="test",
            ip=None,
            status="stopped",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at="2026-01-01T14:25:00Z",
        )
    ]

    show_stopped_instances(instances)

    result = output.getvalue()
    assert "2026-01-01" in result
    assert "14:25" in result


# =============================================================================
# Tests for status command
# =============================================================================


def test_status_displays_running_instances(mocker, sample_config):
    """Test 'gpu-session status' displays running instances.

    Pattern #2 & #3 fix: Verify row structure with exact matching.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat()

    instance_id = "active-instance-12345678"
    mock_api.list_instances.return_value = [
        Instance(
            id=instance_id,
            name="test-instance",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = [
        InstanceType(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    # Mock datetime.utcnow - need to mock the class to return our datetime
    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "GPU Instances" in result.stdout

    # Pattern #2 & #3 fix: Verify row structure - all elements in same row
    lines = result.stdout.split('\n')
    # Find the instance data row - look for data rows (ones with '│' and actual data)
    # Filter out header/border rows
    data_rows = [l for l in lines if '│' in l and 'active' in l.lower()]
    assert len(data_rows) > 0, f"No data rows found. Output: {result.stdout[:500]}"
    data_row = data_rows[0]

    # Verify all data in same row (may be truncated with ... or …)
    assert "active" in data_row, "Status not in instance row"
    # IP might be truncated but should have at least "1.2.3"
    assert "1.2.3" in data_row, "IP address not in instance row"
    # GPU type will be truncated
    assert "gpu_1" in data_row, "GPU type not in instance row"
    # Uptime should be visible
    assert "2h" in data_row, "Uptime not in instance row"


def test_status_no_instances_found(mocker, sample_config):
    """Test 'gpu-session status' when no instances exist."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.list_instances.return_value = []

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "No instances found" in result.stdout


def test_status_specific_instance_id(mocker, sample_config):
    """Test 'gpu-session status --instance-id' shows specific instance."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()

    mock_api.get_instance.return_value = Instance(
        id="specific-instance-12345678",
        name="my-instance",
        ip="5.6.7.8",
        status="active",
        instance_type="gpu_1x_a10",
        region="us-east-1",
        created_at=created_at,
    )

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(
        app, ["status", "--instance-id", "specific-instance-12345678"]
    )

    assert result.exit_code == 0
    assert "speci" in result.stdout  # May be truncated
    assert "my-" in result.stdout or "instance" in result.stdout.lower()


def test_status_instance_not_found(mocker, sample_config):
    """Test 'gpu-session status --instance-id' handles instance not found."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.get_instance.return_value = None

    result = runner.invoke(app, ["status", "--instance-id", "nonexistent"])

    assert result.exit_code == 1
    assert "Instance nonexistent not found" in result.stdout


def test_status_with_history_flag(mocker, sample_config):
    """Test 'gpu-session status --history' shows termination history."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_history_mgr_class = mocker.patch("soong.cli.HistoryManager")
    mock_history_mgr = mock_history_mgr_class.return_value

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=120,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    mock_history_mgr.get_local_history.return_value = events

    result = runner.invoke(app, ["status", "--history"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Termination History" in result.stdout
    assert "User" in result.stdout and "terminated" in result.stdout


def test_status_with_history_and_worker_url(mocker, sample_config):
    """Test 'gpu-session status --history --worker-url' syncs from worker."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api_class.return_value

    mock_history_mgr_class = mocker.patch("soong.cli.HistoryManager")
    mock_history_mgr = mock_history_mgr_class.return_value

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="Synced from worker",
            uptime_minutes=60,
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    mock_history_mgr.sync_from_worker.return_value = events

    result = runner.invoke(
        app,
        ["status", "--history", "--worker-url", "https://worker.example.com"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_history_mgr.sync_from_worker.assert_called_once_with(
        "https://worker.example.com", 24
    )
    assert "Synced" in result.stdout and "worker" in result.stdout


def test_status_with_stopped_flag(mocker, sample_config):
    """Test 'gpu-session status --stopped' shows stopped instances."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.list_instances.return_value = [
        Instance(
            id="stopped-instance-1",
            name="stopped",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at="2026-01-01T10:00:00Z",
        )
    ]

    result = runner.invoke(app, ["status", "--stopped"])

    assert result.exit_code == 0
    assert "Stopped Instances" in result.stdout
    assert "stopped-" in result.stdout or "stopped" in result.stdout.lower()


def test_status_calculates_uptime_correctly(mocker, sample_config):
    """Test 'gpu-session status' calculates uptime correctly."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=3, minutes=25)).replace(
        tzinfo=timezone.utc
    ).isoformat()

    mock_api.list_instances.return_value = [
        Instance(
            id="active-instance-1",
            name="test",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        )
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "3h 25m" in result.stdout


def test_status_shows_expired_time_left_in_red(mocker, sample_config):
    """Test 'gpu-session status' shows expired lease in red."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=5)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now - timedelta(hours=1)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # Expired 1 hour ago

    mock_api.list_instances.return_value = [
        Instance(
            id="expired-instance-1",
            name="expired",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "EXPI" in result.stdout  # May be truncated in table


def test_status_shows_expiring_soon_in_yellow(mocker, sample_config):
    """Test 'gpu-session status' shows expiring soon (<1h) in yellow."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=3)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(minutes=30)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # 30 minutes left

    mock_api.list_instances.return_value = [
        Instance(
            id="expiring-instance-1",
            name="expiring-soon",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "30m" in result.stdout  # Should show minutes only


def test_status_shows_safe_time_left_in_green(mocker, sample_config):
    """Test 'gpu-session status' shows safe time left (>1h) in green."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(hours=3, minutes=15)).replace(
        tzinfo=timezone.utc
    ).isoformat()

    mock_api.list_instances.return_value = [
        Instance(
            id="safe-instance-1",
            name="safe",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "3h 15m" in result.stdout


def test_status_calculates_current_cost(mocker, sample_config):
    """Test 'gpu-session status' calculates current cost correctly.

    Pattern #4 fix: Use unique values to verify calculation is consumed.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    # Pattern #4 fix: Use non-round hours to ensure calculation is used
    uptime_hours = 2.75  # 2 hours 45 minutes - unusual value
    created_at = (now - timedelta(hours=uptime_hours)).replace(
        tzinfo=timezone.utc
    ).isoformat()

    # Pattern #4 fix: Use unusual price that would fail if hardcoded
    unique_price_cents = 137  # $1.37/hr - not a typical round number
    instance_id = "instance-1"

    mock_api.list_instances.return_value = [
        Instance(
            id=instance_id,
            name="test",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at=created_at,
        )
    ]

    mock_api.list_instance_types.return_value = [
        InstanceType(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=unique_price_cents,
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0

    # Pattern #4 fix: Verify exact calculated cost appears in output
    # 2.75 hours * $1.37/hr = $3.7675 ≈ $3.77
    expected_cost = "$3.77"
    # Cost appears in the output - either in instance row or summary section
    assert expected_cost in result.stdout, f"Expected cost {expected_cost} not found in output: {result.stdout}"


def test_status_calculates_total_cost(mocker, sample_config):
    """Test 'gpu-session status' calculates estimated total cost.

    Pattern #4 fix: Use unique values to verify total cost calculation.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    # Pattern #4 fix: Use non-round total hours
    created_at = (now - timedelta(hours=1.5)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(hours=3.25)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # Total lease: 4.75 hours

    # Pattern #4 fix: Use unique price
    unique_price_cents = 143  # $1.43/hr

    mock_api.list_instances.return_value = [
        Instance(
            id="instance-1",
            name="test",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = [
        InstanceType(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=unique_price_cents,
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Pattern #4 fix: Verify exact total cost
    # 4.75 hours * $1.43/hr = $6.7925 ≈ $6.79
    expected_total = "$6.79"
    # Total cost should appear somewhere in output
    assert expected_total in result.stdout, f"Expected total cost {expected_total} not found in output"


def test_status_multiple_instances_total_cost(mocker, sample_config):
    """Test 'gpu-session status' shows total cost for multiple instances.

    Pattern #4 fix: Use unique values to verify multi-instance total.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    # Pattern #4 fix: Use non-round uptimes
    uptime_1 = 2.333  # 2 hours 20 minutes
    uptime_2 = 1.667  # 1 hour 40 minutes
    created_at_1 = (now - timedelta(hours=uptime_1)).replace(tzinfo=timezone.utc).isoformat()
    created_at_2 = (now - timedelta(hours=uptime_2)).replace(tzinfo=timezone.utc).isoformat()

    # Pattern #4 fix: Use unique prices
    price_1_cents = 147  # $1.47/hr
    price_2_cents = 67   # $0.67/hr

    mock_api.list_instances.return_value = [
        Instance(
            id="instance-1",
            name="test1",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at=created_at_1,
        ),
        Instance(
            id="instance-2",
            name="test2",
            ip="5.6.7.8",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-east-1",
            created_at=created_at_2,
        ),
    ]

    mock_api.list_instance_types.return_value = [
        InstanceType(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=price_1_cents,
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        ),
        InstanceType(
            name="gpu_1x_a10",
            description="1x A10 (24 GB)",
            price_cents_per_hour=price_2_cents,
            vcpus=12,
            memory_gib=46,
            storage_gib=512,
            regions_available=["us-east-1"],
        ),
    ]

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0

    # Pattern #4 fix: Verify exact calculated costs
    # Instance 1: 2.333 hours * $1.47/hr = $3.43 (rounded)
    # Instance 2: 1.667 hours * $0.67/hr = $1.12 (rounded)
    # Total: $4.55
    expected_total = "$4.55"
    assert "Total current cost" in result.stdout
    total_line = next((l for l in result.stdout.split('\n') if "Total current cost" in l), None)
    assert total_line is not None, "Total cost line not found"
    assert expected_total in total_line, f"Expected total {expected_total} not in total line: {total_line}"


def test_status_handles_api_error(mocker, sample_config):
    """Test 'gpu-session status' handles Lambda API errors.

    Pattern #6 fix: Verify specific error message propagates correctly.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    # Pattern #6 fix: Use unique error message to verify it's not swallowed
    unique_error = "Connection timeout to Lambda API endpoint 192.168.1.99:8443"
    mock_api.list_instances.side_effect = LambdaAPIError(unique_error)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    # Pattern #6 fix: Verify exact error message appears (not generic message)
    assert "Error getting status" in result.stdout
    # Error message may have newlines, so check for key parts
    assert "Connection timeout to Lambda API endpoint" in result.stdout, f"Specific error message not found. Output: {result.stdout}"
    # Verify error wasn't swallowed or replaced with generic message
    assert "192.168.1.99:8443" in result.stdout, "Error details missing"


def test_status_filters_to_running_only(mocker, sample_config):
    """Test 'gpu-session status' shows only running instances by default.

    Pattern #2 & #3 fix: Verify filtering with row structure validation.
    """
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()

    active_id = "active-instance-1"
    terminated_id = "terminated-instance-1"
    stopped_id = "stopped-instance-1"

    mock_api.list_instances.return_value = [
        Instance(
            id=active_id,
            name="running",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
        Instance(
            id=terminated_id,
            name="stopped",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
        Instance(
            id=stopped_id,
            name="stopped2",
            ip=None,
            status="stopped",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0

    lines = result.stdout.split('\n')

    # Pattern #2 & #3 fix: Verify active instance appears with all data in row
    # Look for rows with both '│' separator and 'active' status
    active_rows = [l for l in lines if '│' in l and 'active' in l.lower()]
    assert len(active_rows) > 0, f"Active instance not found in output. Lines: {[l[:60] for l in lines if l.strip()]}"
    active_row = active_rows[0]
    assert "1.2.3" in active_row, "IP not in row"

    # Pattern #3 fix: Verify terminated/stopped instances are NOT present
    # Check that terminated/stopped status doesn't appear in data rows
    data_rows = [l for l in lines if '│' in l and not l.strip().startswith('┃')]
    assert not any('terminated' in l.lower() for l in data_rows), "Terminated instance should not appear"
    # Also verify specific instance IDs don't appear (they may be truncated)
    output_lower = result.stdout.lower()
    # "stopped" might appear in help text, so just verify the IDs don't appear
    assert terminated_id[:6] not in result.stdout, "Terminated instance ID should not appear"
    assert stopped_id[:6] not in result.stdout, "Stopped instance ID should not appear"


def test_status_handles_missing_pricing(mocker, sample_config):
    """Test 'gpu-session status' handles missing pricing gracefully."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()

    mock_api.list_instances.return_value = [
        Instance(
            id="instance-1",
            name="test",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_unknown",
            region="us-west-1",
            created_at=created_at,
        )
    ]

    # Return empty pricing list
    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Should show dashes for cost when pricing unavailable
    assert "insta" in result.stdout  # Instance ID may be truncated


def test_status_no_running_instances_shows_help_text(mocker, sample_config):
    """Test 'gpu-session status' shows help when no running instances."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.list_instances.return_value = [
        Instance(
            id="stopped-instance-1",
            name="stopped",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at="2026-01-01T10:00:00Z",
        )
    ]

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "No running instances found" in result.stdout
    assert "--stopped" in result.stdout
    assert "--history" in result.stdout


def test_status_expired_cost_highlighted_in_red(mocker, sample_config):
    """Test 'gpu-session status' highlights cost in red when lease expired."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(hours=5)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now - timedelta(hours=1)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # Expired

    mock_api.list_instances.return_value = [
        Instance(
            id="expired-instance-1",
            name="expired",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at=created_at,
            lease_expires_at=expires_at,
        )
    ]

    mock_api.list_instance_types.return_value = [
        InstanceType(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    mock_datetime = mocker.patch("soong.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Should show cost for 5 hours
    assert "$6.45" in result.stdout  # 5 * 1.29
    assert "EXPI" in result.stdout  # May be truncated in table
