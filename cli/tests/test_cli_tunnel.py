"""Tests for 'gpu-session tunnel' CLI commands."""

import pytest
from unittest.mock import Mock
from typer.testing import CliRunner
from soong.cli import app
from soong.lambda_api import Instance


runner = CliRunner()


# Helper function to mock subprocess for SSH tunnels
def mock_subprocess_for_tunnel(mocker):
    """Mock subprocess.run to handle SSH and pgrep calls."""
    ssh_result = Mock()
    ssh_result.returncode = 0
    ssh_result.stderr = ""

    pgrep_result = Mock()
    pgrep_result.returncode = 0
    pgrep_result.stdout = "12345"

    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.side_effect = [ssh_result, pgrep_result]

    return mock_subprocess


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
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_api.return_value.get_instance.assert_called_once_with("i-test-123")

    # Verify SSH command structure (first call)
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert ssh_call_args[0] == "ssh"
    assert "-N" in ssh_call_args
    assert "-f" in ssh_call_args
    assert "-i" in ssh_call_args
    assert f"ubuntu@{mock_instance.ip}" in ssh_call_args

    # Verify port forwarding arguments
    assert "-L" in ssh_call_args
    assert "8000:localhost:8000" in ssh_call_args
    assert "5678:localhost:5678" in ssh_call_args
    assert "8080:localhost:8080" in ssh_call_args


def test_tunnel_start_success_with_active_instance(mocker, sample_config, mock_instance):
    """Test 'tunnel start' without instance_id uses active instance."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
    mock_instance_mgr.return_value.get_active_instance.return_value = mock_instance

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(app, ["tunnel", "start"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_instance_mgr.return_value.get_active_instance.assert_called_once()

    # Verify SSH command structure
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert ssh_call_args[0] == "ssh"
    assert f"ubuntu@{mock_instance.ip}" in ssh_call_args
    assert "8000:localhost:8000" in ssh_call_args
    assert "5678:localhost:5678" in ssh_call_args
    assert "8080:localhost:8080" in ssh_call_args


def test_tunnel_start_custom_sglang_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom sglang_port."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--sglang-port", "9000"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify custom port forwarding: local 9000 -> remote 8000
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "9000:localhost:8000" in ssh_call_args
    assert "5678:localhost:5678" in ssh_call_args
    assert "8080:localhost:8080" in ssh_call_args


def test_tunnel_start_custom_n8n_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom n8n_port."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--n8n-port", "6000"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify custom port forwarding: local 6000 -> remote 5678
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "8000:localhost:8000" in ssh_call_args
    assert "6000:localhost:5678" in ssh_call_args
    assert "8080:localhost:8080" in ssh_call_args


def test_tunnel_start_custom_status_port(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with custom status_port."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--status-port", "9090"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify custom port forwarding: local 9090 -> remote 8080
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "8000:localhost:8000" in ssh_call_args
    assert "5678:localhost:5678" in ssh_call_args
    assert "9090:localhost:8080" in ssh_call_args


def test_tunnel_start_all_custom_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' with all custom ports."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

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

    # Verify all custom port forwarding
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "9000:localhost:8000" in ssh_call_args
    assert "6000:localhost:5678" in ssh_call_args
    assert "9090:localhost:8080" in ssh_call_args


def test_tunnel_start_no_instance_found_with_id(mocker, sample_config):
    """Test 'tunnel start' exits when instance_id not found."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = None

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-nonexistent"],
    )

    assert result.exit_code == 1
    assert "No instance found" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_no_active_instance(mocker, sample_config):
    """Test 'tunnel start' exits when no active instance found."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
    mock_instance_mgr.return_value.get_active_instance.return_value = None

    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")

    result = runner.invoke(app, ["tunnel", "start"])

    assert result.exit_code == 1
    assert "No instance found" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_instance_no_ip(mocker, sample_config, mock_instance_no_ip):
    """Test 'tunnel start' exits when instance has no IP address."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance_no_ip

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-456"],
    )

    assert result.exit_code == 1
    assert "Instance has no IP address" in result.stdout
    mock_ssh_mgr.return_value.start_tunnel.assert_not_called()


def test_tunnel_start_calls_start_tunnel(mocker, sample_config, mock_instance):
    """Test 'tunnel start' constructs correct SSH command with all required flags."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level to verify SSH command construction
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify exact SSH command structure
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert ssh_call_args[0] == "ssh"
    assert "-N" in ssh_call_args  # No remote command
    assert "-f" in ssh_call_args  # Background
    assert "-i" in ssh_call_args  # Identity file

    # Verify SSH key path is expanded (path will be expanded by Path.expanduser())
    key_path_index = ssh_call_args.index("-i") + 1
    assert ".ssh/id_rsa" in str(ssh_call_args[key_path_index])  # Path is expanded, check for core part

    # Verify user@host format
    assert f"ubuntu@{mock_instance.ip}" in ssh_call_args


def test_tunnel_start_failure_exits_1(mocker, sample_config, mock_instance):
    """Test 'tunnel start' exits with code 1 when start_tunnel fails."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.start_tunnel.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
    )

    assert result.exit_code == 1


def test_tunnel_start_default_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' uses default ports when none specified."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify default port forwarding (local == remote)
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "8000:localhost:8000" in ssh_call_args
    assert "5678:localhost:5678" in ssh_call_args
    assert "8080:localhost:8080" in ssh_call_args


def test_tunnel_start_passes_correct_remote_ports(mocker, sample_config, mock_instance):
    """Test 'tunnel start' always passes correct remote ports regardless of local ports."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

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

    # Verify remote ports are always 8000, 5678, 8080 regardless of local ports
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "9999:localhost:8000" in ssh_call_args  # Custom local -> standard remote
    assert "7777:localhost:5678" in ssh_call_args  # Custom local -> standard remote
    assert "6666:localhost:8080" in ssh_call_args  # Custom local -> standard remote


# tunnel stop tests


def test_tunnel_stop_success(mocker, sample_config):
    """Test 'tunnel stop' successfully stops tunnel."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = True

    result = runner.invoke(app, ["tunnel", "stop"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_ssh_mgr.return_value.stop_tunnel.assert_called_once()


def test_tunnel_stop_failure_exits_1(mocker, sample_config):
    """Test 'tunnel stop' exits with code 1 when stop_tunnel fails."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = False

    result = runner.invoke(app, ["tunnel", "stop"])

    assert result.exit_code == 1


def test_tunnel_stop_calls_stop_tunnel(mocker, sample_config):
    """Test 'tunnel stop' calls SSHTunnelManager.stop_tunnel."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.stop_tunnel.return_value = True

    result = runner.invoke(app, ["tunnel", "stop"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)
    mock_ssh_mgr.return_value.stop_tunnel.assert_called_once()


# tunnel status tests


def test_tunnel_status_running(mocker, sample_config):
    """Test 'tunnel status' shows correct message and exit code when tunnel is active."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock SSHTunnelManager at CLI level
    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = True

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    # Verify both exit code and output message
    assert result.exit_code == 0
    assert "Tunnel is running" in result.stdout
    assert "not running" not in result.stdout.lower()

    # Verify correct SSH key path was passed to manager
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)

    # Verify is_tunnel_running was called
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once()


def test_tunnel_status_not_running(mocker, sample_config):
    """Test 'tunnel status' shows correct message and exit code when tunnel is inactive."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock SSHTunnelManager at CLI level
    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = False

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    # Verify both exit code and output message
    assert result.exit_code == 0
    assert "Tunnel is not running" in result.stdout
    assert "is running" not in result.stdout or "not running" in result.stdout

    # Verify correct SSH key path was passed to manager
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)

    # Verify is_tunnel_running was called
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once()


def test_tunnel_status_calls_is_tunnel_running(mocker, sample_config):
    """Test 'tunnel status' calls SSHTunnelManager with correct SSH key path."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock SSHTunnelManager at CLI level
    mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
    mock_ssh_mgr.return_value.is_tunnel_running.return_value = True

    result = runner.invoke(app, ["tunnel", "status"], catch_exceptions=False)

    assert result.exit_code == 0

    # Verify SSHTunnelManager was initialized with correct key path
    mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)

    # Verify is_tunnel_running method was called exactly once
    mock_ssh_mgr.return_value.is_tunnel_running.assert_called_once_with()


# Port validation edge case tests (Pattern #8 - Branch Coverage)


def test_tunnel_start_invalid_port_below_range(mocker, sample_config, mock_instance):
    """Test 'tunnel start' rejects ports below valid range (< 1)."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    # Attempt to use invalid port (0)
    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--sglang-port", "0"],
    )

    # Typer should reject invalid port before we even get to tunnel logic
    assert result.exit_code != 0


def test_tunnel_start_invalid_port_above_range(mocker, sample_config, mock_instance):
    """Test 'tunnel start' rejects ports above valid range (> 65535)."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    # Attempt to use invalid port (65536)
    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--n8n-port", "65536"],
    )

    # Typer should reject invalid port before we even get to tunnel logic
    assert result.exit_code != 0


def test_tunnel_start_port_boundary_low(mocker, sample_config, mock_instance):
    """Test 'tunnel start' accepts minimum valid port (1)."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--status-port", "1"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify port 1 is used
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "1:localhost:8080" in ssh_call_args


def test_tunnel_start_port_boundary_high(mocker, sample_config, mock_instance):
    """Test 'tunnel start' accepts maximum valid port (65535)."""
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    mock_api = mocker.patch("soong.cli.LambdaAPI")
    mock_api.return_value.get_instance.return_value = mock_instance

    mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")

    # Mock at subprocess level
    mock_subprocess = mock_subprocess_for_tunnel(mocker)

    mock_is_running = mocker.patch("soong.ssh.SSHTunnelManager.is_tunnel_running")
    mock_is_running.return_value = False

    result = runner.invoke(
        app,
        ["tunnel", "start", "--instance-id", "i-test-123", "--sglang-port", "65535"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0

    # Verify port 65535 is used
    ssh_call_args = mock_subprocess.call_args_list[0][0][0]
    assert "65535:localhost:8000" in ssh_call_args
