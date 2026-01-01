"""Tests for 'gpu-session tunnel' CLI commands."""

import pytest
from typer.testing import CliRunner
from gpu_session.cli import app
from gpu_session.lambda_api import Instance


runner = CliRunner()


# Fixtures


@pytest.fixture
def mock_instance():
    """Mock instance with IP."""
    return Instance(
        id="i-test-123",
        name="test-instance",
        ip="192.168.1.100",
        status="active",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def mock_instance_no_ip():
    """Mock instance without IP."""
    return Instance(
        id="i-test-456",
        name="test-instance-no-ip",
        ip=None,
        status="pending",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z",
    )


# tunnel start tests


def test_tunnel_start_success_with_instance_id(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with specific instance_id successfully starts tunnel."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_api.return_value.get_instance.assert_called_once_with("i-test-123")
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[8000, 5678, 8080],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_success_with_active_instance(mocker, sample_config, mock_instance):
    """Test 'tunnel start' without instance_id uses active instance."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")
    mock_instance_mgr.return_value.get_active_instance.return_value = mock_instance

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(app, ["tunnel", "start"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_instance_mgr.return_value.get_active_instance.assert_called_once()
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[8000, 5678, 8080],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_custom_sglang_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom sglang_port."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--sglang-port", "9000"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[9000, 5678, 8080],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_custom_n8n_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom n8n_port."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--n8n-port", "6000"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[8000, 6000, 8080],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_custom_status_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom status_port."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--status-port", "9090"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[8000, 5678, 9090],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_all_custom_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with all custom ports."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        [
            "tunnel",
            "start",
            "--instance-id",
            "i-test-123",
            "--sglang-port",
            "9000",
            "--n8n-port",
            "6000",
            "--status-port",
            "9090",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once_with(
        "192.168.1.100",
        local_ports=[9000, 6000, 9090],
        remote_ports=[8000, 5678, 8080],
    )


def test_tunnel_start_no_instance_found_with_id(mocker, sample_config):
    """Test 'tunnel start' exits when instance_id not found."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = None

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")
    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-nonexistent"],
    )

    assert result.exit_code == 1
    assert "No instance found" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_no_active_instance(mocker, sample_config):
    """Test 'tunnel start' exits when no active instance found."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")
    mock_instance_mgr.return_value.get_active_instance.return_value = None

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")

    result = runner.invoke(app, ["tunnel", "start"])

    assert result.exit_code == 1
    assert "No instance found" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_instance_no_ip(mocker, sample_config, mock_instance_no_ip):
    """Test 'tunnel start' exits when instance has no IP address."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance_no_ip

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")
    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-456"],
    )

    assert result.exit_code == 1
    assert "Instance has no IP address" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_calls_start_tunnel(mocker, sample_config, mock_instance):
    """Test 'tunnel start' calls SSHTunnelManager.start_tunnel with correct parameters."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)
    mock_ssh_mgr.return_value.start_tunnel.assert_called_once()


def test_tunnel_start_failure_exits_1(mocker, sample_config, mock_instance):
    """Test 'tunnel start' exits with code 1 when start_tunnel fails."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
    )

    assert result.exit_code == 1


def test_tunnel_start_default_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' uses default ports when none specified."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    call_args = mock_ssh_mgr.return_value.start_tunnel.call_args
    assert call_args[1]["local_ports"] == [8000, 5678, 8080]
    assert call_args[1]["remote_ports"] == [8000, 5678, 8080]


def test_tunnel_start_passes_correct_remote_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' always passes correct remote ports regardless of local ports."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("gpu_session.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("gpu_session.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = True

    result = runner.invoke(
        app,
        [
            "tunnel",
            "start",
            "--instance-id",
            "i-test-123",
            "--sglang-port",
            "9999",
            "--n8n-port",
            "7777",
            "--status-port",
            "6666",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    call_args = mock_ssh_mgr.return_value.start_tunnel.call_args
    assert call_args[1]["local_ports"] == [9999, 7777, 6666]
    assert call_args[1]["remote_ports"] == [8000, 5678, 8080]


# tunnel stop tests


def test_tunnel_stop_success(mocker, sample_config):
    """Test 'tunnel stop' successfully stops tunnel."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = True

    result = runner.invoke(app, ["tunnel", "stop"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.stop_tunnel.assert_called_once()


def test_tunnel_stop_failure_exits_1(mocker, sample_config):
    """Test 'tunnel stop' exits with code 1 when stop_tunnel fails."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = False

    result = runner.invoke(app, ["tunnel", "stop"])

    assert result.exit_code == 1


def test_tunnel_stop_calls_stop_tunnel(mocker, sample_config):
    """Test 'tunnel stop' calls SSHTunnelManager.stop_tunnel."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = True

    result = runner.invoke(app, ["tunnel", "stop"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)
    mock_ssh_mgr.return_value.stop_tunnel.assert_called_once()


# tunnel status tests


def test_tunnel_status_running(mocker, sample_config):
    """Test 'tunnel status' shows running message when tunnel is active."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = True

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Tunnel is running" in result.stdout
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once()


def test_tunnel_status_not_running(mocker, sample_config):
    """Test 'tunnel status' shows not running message when tunnel is inactive."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = False

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Tunnel is not running" in result.stdout
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once()


def test_tunnel_status_calls_is_tunnel_running(mocker, sample_config):
    """Test 'tunnel status' calls SSHTunnelManager.is_tunnel_running."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("gpu_session.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = True

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once()
