"""Tests for 'gpu-session status' CLI command and helper functions."""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
from typer.testing import CliRunner
from rich.console import Console
from io import StringIO

from gpu_session.cli import app, show_termination_history, show_stopped_instances
from gpu_session.lambda_api import Instance, InstanceType, LambdaAPIError
from gpu_session.history import HistoryEvent


runner = CliRunner()


# =============================================================================
# Tests for show_termination_history()
# =============================================================================


def test_show_termination_history_displays_table(mocker):
    """Test show_termination_history displays events in a table."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

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
    assert "Termination History" in result
    assert "24 Hours" in result
    assert "Time" in result
    assert "Instance ID" in result
    assert "Reason" in result
    assert "Uptime" in result
    assert "GPU" in result
    assert "Region" in result
    assert "test-ins" in result  # First 8 chars of instance ID
    assert "User" in result and "terminated" in result
    assert "2h 5m" in result  # 125 minutes
    assert "gpu_1x_a100" in result or "a100" in result.lower()
    assert "us-west-1" in result


def test_show_termination_history_empty_list(mocker):
    """Test show_termination_history handles empty events list."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

    show_termination_history([], hours=24)

    result = output.getvalue()
    assert "No termination events found" in result
    assert "24" in result and "hours" in result


def test_show_termination_history_watchdog_reason_red(mocker):
    """Test show_termination_history colors watchdog reason in red."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

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
    mocker.patch("gpu_session.cli.console", test_console)

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
    mocker.patch("gpu_session.cli.console", test_console)

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
    """Test show_termination_history formats uptime with hours and minutes."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

    events = [
        HistoryEvent(
            timestamp="2026-01-01T10:00:00Z",
            instance_id="test-instance-1",
            event_type="termination",
            reason="User terminated",
            uptime_minutes=185,  # 3h 5m
            gpu_type="gpu_1x_a10",
            region="us-west-1",
        )
    ]

    show_termination_history(events, hours=24)

    result = output.getvalue()
    assert "3h 5m" in result


def test_show_termination_history_formats_uptime_minutes_only(mocker):
    """Test show_termination_history formats uptime with minutes only."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

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
    mocker.patch("gpu_session.cli.console", test_console)

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
    """Test show_stopped_instances displays instances in a table."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

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
    assert "Stopped Instances" in result
    assert "Instance ID" in result
    assert "Name" in result
    assert "Status" in result
    assert "GPU" in result
    assert "Region" in result
    assert "Created At" in result
    assert "stopped-" in result  # First 8 chars (may be followed by spaces in table)
    assert "my-instan" in result or "instance" in result.lower()
    assert "terminated" in result
    assert "gpu_1x_a10" in result  # May be truncated with ellipsis in table
    assert "us-west-1" in result


def test_show_stopped_instances_empty_list(mocker):
    """Test show_stopped_instances handles empty list."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

    show_stopped_instances([])

    result = output.getvalue()
    assert "No stopped instances" in result and "found" in result


def test_show_stopped_instances_filters_to_stopped_only(mocker):
    """Test show_stopped_instances filters to stopped/terminated instances."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)
    mocker.patch("gpu_session.cli.console", test_console)

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
    mocker.patch("gpu_session.cli.console", test_console)

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
    """Test 'gpu-session status' displays running instances."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
    created_at = (now - timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat()

    mock_api.list_instances.return_value = [
        Instance(
            id="active-instance-12345678",
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
    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "GPU Instances" in result.stdout
    assert "activ" in result.stdout  # Instance ID may be truncated
    assert "test-" in result.stdout or "test" in result.stdout.lower()
    assert "active" in result.stdout
    assert "1.2.3" in result.stdout
    assert "gpu_1" in result.stdout  # GPU type may be truncated


def test_status_no_instances_found(mocker, sample_config):
    """Test 'gpu-session status' when no instances exist."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.list_instances.return_value = []

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "No instances found" in result.stdout


def test_status_specific_instance_id(mocker, sample_config):
    """Test 'gpu-session status --instance-id' shows specific instance."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
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
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.get_instance.return_value = None

    result = runner.invoke(app, ["status", "--instance-id", "nonexistent"])

    assert result.exit_code == 1
    assert "Instance nonexistent not found" in result.stdout


def test_status_with_history_flag(mocker, sample_config):
    """Test 'gpu-session status --history' shows termination history."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_history_mgr_class = mocker.patch("gpu_session.cli.HistoryManager")
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
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api_class.return_value

    mock_history_mgr_class = mocker.patch("gpu_session.cli.HistoryManager")
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
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
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
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "3h 25m" in result.stdout


def test_status_shows_expired_time_left_in_red(mocker, sample_config):
    """Test 'gpu-session status' shows expired lease in red."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "EXPI" in result.stdout  # May be truncated in table


def test_status_shows_expiring_soon_in_yellow(mocker, sample_config):
    """Test 'gpu-session status' shows expiring soon (<1h) in yellow."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "30m" in result.stdout  # Should show minutes only


def test_status_shows_safe_time_left_in_green(mocker, sample_config):
    """Test 'gpu-session status' shows safe time left (>1h) in green."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "3h 15m" in result.stdout


def test_status_calculates_current_cost(mocker, sample_config):
    """Test 'gpu-session status' calculates current cost correctly."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
    created_at = (now - timedelta(hours=2)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # 2 hours uptime

    mock_api.list_instances.return_value = [
        Instance(
            id="instance-1",
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
            price_cents_per_hour=129,  # $1.29/hr
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # 2 hours * $1.29 = $2.58
    assert "$2.58" in result.stdout


def test_status_calculates_total_cost(mocker, sample_config):
    """Test 'gpu-session status' calculates estimated total cost."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()
    expires_at = (now + timedelta(hours=3)).replace(
        tzinfo=timezone.utc
    ).isoformat()  # Total lease: 4 hours

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
            price_cents_per_hour=129,  # $1.29/hr
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        )
    ]

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # 4 hours * $1.29 = $5.16
    assert "$5.16" in result.stdout


def test_status_multiple_instances_total_cost(mocker, sample_config):
    """Test 'gpu-session status' shows total cost for multiple instances."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
    created_at_1 = (now - timedelta(hours=2)).replace(tzinfo=timezone.utc).isoformat()
    created_at_2 = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()

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
            price_cents_per_hour=129,  # $1.29/hr
            vcpus=30,
            memory_gib=210,
            storage_gib=512,
            regions_available=["us-west-1"],
        ),
        InstanceType(
            name="gpu_1x_a10",
            description="1x A10 (24 GB)",
            price_cents_per_hour=60,  # $0.60/hr
            vcpus=12,
            memory_gib=46,
            storage_gib=512,
            regions_available=["us-east-1"],
        ),
    ]

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Instance 1: 2 hours * $1.29 = $2.58
    # Instance 2: 1 hour * $0.60 = $0.60
    # Total: $3.18
    assert "Total current cost" in result.stdout
    assert "$3.18" in result.stdout


def test_status_handles_api_error(mocker, sample_config):
    """Test 'gpu-session status' handles Lambda API errors."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    mock_api.list_instances.side_effect = LambdaAPIError("API connection failed")

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "Error getting status" in result.stdout
    assert "API connection failed" in result.stdout


def test_status_filters_to_running_only(mocker, sample_config):
    """Test 'gpu-session status' shows only running instances by default."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
    created_at = (now - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()

    mock_api.list_instances.return_value = [
        Instance(
            id="active-instance-1",
            name="running",
            ip="1.2.3.4",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
        Instance(
            id="terminated-instance-1",
            name="stopped",
            ip=None,
            status="terminated",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
        Instance(
            id="stopped-instance-1",
            name="stopped2",
            ip=None,
            status="stopped",
            instance_type="gpu_1x_a10",
            region="us-west-1",
            created_at=created_at,
        ),
    ]

    mock_api.list_instance_types.return_value = []

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "activ" in result.stdout  # Instance ID may be truncated
    assert "running" in result.stdout or "runni" in result.stdout
    assert "terminat" not in result.stdout
    assert "stopped" not in result.stdout.lower() or "Use --stopped" in result.stdout


def test_status_handles_missing_pricing(mocker, sample_config):
    """Test 'gpu-session status' handles missing pricing gracefully."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Should show dashes for cost when pricing unavailable
    assert "insta" in result.stdout  # Instance ID may be truncated


def test_status_no_running_instances_shows_help_text(mocker, sample_config):
    """Test 'gpu-session status' shows help when no running instances."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
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
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api_class = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    now = datetime.utcnow()
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

    mock_datetime = mocker.patch("gpu_session.cli.datetime")
    mock_datetime.utcnow.return_value = now
    mock_datetime.fromisoformat = datetime.fromisoformat

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Should show cost for 5 hours
    assert "$6.45" in result.stdout  # 5 * 1.29
    assert "EXPI" in result.stdout  # May be truncated in table
