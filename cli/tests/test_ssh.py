"""Tests for ssh.py SSH tunnel management."""

import pytest
import signal
from pathlib import Path
from unittest.mock import Mock, MagicMock
from gpu_session.ssh import SSHTunnelManager


@pytest.fixture
def ssh_key_path(tmp_path):
    """Temporary SSH key path for testing."""
    key_path = tmp_path / "test_key.pem"
    key_path.write_text("fake ssh key")
    return str(key_path)


@pytest.fixture
def tunnel_manager(ssh_key_path, tmp_path):
    """SSHTunnelManager instance with temporary PID file location."""
    manager = SSHTunnelManager(ssh_key_path)
    # Override PID file location to use tmp_path
    manager.tunnel_pid_file = tmp_path / "tunnel.pid"
    return manager


@pytest.fixture
def instance_ip():
    """Sample instance IP for testing."""
    return "203.0.113.42"


# SSHTunnelManager.__init__ Tests


def test_ssh_tunnel_manager_init_with_expanduser(tmp_path):
    """Test SSHTunnelManager initializes with path expansion."""
    manager = SSHTunnelManager("~/.ssh/id_rsa")
    assert manager.ssh_key_path == Path.home() / ".ssh" / "id_rsa"
    assert manager.tunnel_pid_file == Path.home() / ".config" / "gpu-dashboard" / "tunnel.pid"


def test_ssh_tunnel_manager_init_with_absolute_path(tmp_path):
    """Test SSHTunnelManager initializes with absolute path."""
    key_path = tmp_path / "key.pem"
    manager = SSHTunnelManager(str(key_path))
    assert manager.ssh_key_path == key_path


# start_tunnel() Tests


def test_start_tunnel_mismatched_port_lengths(tunnel_manager, instance_ip):
    """Test start_tunnel rejects mismatched port lengths."""
    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080, 8888],
        remote_ports=[80],  # Mismatched length
    )
    assert result is False


def test_start_tunnel_already_running(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel rejects when tunnel already running."""
    # Mock is_tunnel_running to return True
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=True)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )
    assert result is False


def test_start_tunnel_success(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel successfully starts SSH tunnel."""
    # Mock dependencies
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")

    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080, 8888],
        remote_ports=[80, 443],
        username="testuser",
    )

    # Verify result
    assert result is True

    # Verify SSH command built correctly
    call_args = mock_subprocess.call_args[0][0]
    assert call_args[0] == "ssh"
    assert "-N" in call_args
    assert "-f" in call_args
    assert "-i" in call_args
    assert str(tunnel_manager.ssh_key_path) in call_args
    assert f"testuser@{instance_ip}" in call_args
    assert "-L" in call_args
    assert "8080:localhost:80" in call_args
    assert "8888:localhost:443" in call_args

    # Verify PID file created
    assert tunnel_manager.tunnel_pid_file.exists()
    assert tunnel_manager.tunnel_pid_file.read_text() == "12345"


def test_start_tunnel_success_without_pid(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel succeeds even if PID not found."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=None)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    assert result is True
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_start_tunnel_ssh_command_failed(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel handles SSH command failure."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=255,
        stderr="Permission denied (publickey)."
    )

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    assert result is False


def test_start_tunnel_timeout(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel handles timeout."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = __import__("subprocess").TimeoutExpired(
        cmd="ssh", timeout=30
    )

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    assert result is False


def test_start_tunnel_unexpected_exception(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel handles unexpected exceptions."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = OSError("Network unreachable")

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    assert result is False


def test_start_tunnel_default_username(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel uses default username 'ubuntu'."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    call_args = mock_subprocess.call_args[0][0]
    assert f"ubuntu@{instance_ip}" in call_args


def test_start_tunnel_creates_pid_file_directory(tunnel_manager, instance_ip, mocker, tmp_path):
    """Test start_tunnel creates PID file directory if missing."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    # Set PID file in non-existent directory
    tunnel_manager.tunnel_pid_file = tmp_path / "nested" / "dir" / "tunnel.pid"

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    assert result is True
    assert tunnel_manager.tunnel_pid_file.exists()
    assert tunnel_manager.tunnel_pid_file.parent.exists()


# stop_tunnel() Tests


def test_stop_tunnel_no_pid_file(tunnel_manager):
    """Test stop_tunnel returns False when no PID file exists."""
    result = tunnel_manager.stop_tunnel()
    assert result is False


def test_stop_tunnel_success(tunnel_manager, mocker):
    """Test stop_tunnel successfully stops tunnel."""
    # Create PID file
    tunnel_manager.tunnel_pid_file.write_text("12345")

    # Mock os.kill
    mock_kill = mocker.patch("gpu_session.ssh.os.kill")

    result = tunnel_manager.stop_tunnel()

    # Verify result
    assert result is True

    # Verify os.kill called with correct arguments
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    # Verify PID file removed
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_stop_tunnel_process_not_found(tunnel_manager, mocker):
    """Test stop_tunnel handles ProcessLookupError (stale PID)."""
    tunnel_manager.tunnel_pid_file.write_text("99999")

    # Mock os.kill to raise ProcessLookupError
    mock_kill = mocker.patch("gpu_session.ssh.os.kill")
    mock_kill.side_effect = ProcessLookupError()

    result = tunnel_manager.stop_tunnel()

    # Should still return True and clean up PID file
    assert result is True
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_stop_tunnel_invalid_pid_format(tunnel_manager):
    """Test stop_tunnel handles invalid PID file content."""
    tunnel_manager.tunnel_pid_file.write_text("not-a-number")

    result = tunnel_manager.stop_tunnel()

    assert result is False


def test_stop_tunnel_permission_error(tunnel_manager, mocker):
    """Test stop_tunnel handles permission errors."""
    tunnel_manager.tunnel_pid_file.write_text("12345")

    mock_kill = mocker.patch("gpu_session.ssh.os.kill")
    mock_kill.side_effect = PermissionError("Operation not permitted")

    result = tunnel_manager.stop_tunnel()

    assert result is False
    # PID file should not be removed on error
    assert tunnel_manager.tunnel_pid_file.exists()


def test_stop_tunnel_whitespace_in_pid(tunnel_manager, mocker):
    """Test stop_tunnel handles whitespace in PID file."""
    tunnel_manager.tunnel_pid_file.write_text("  12345  \n")

    mock_kill = mocker.patch("gpu_session.ssh.os.kill")

    result = tunnel_manager.stop_tunnel()

    assert result is True
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)


# is_tunnel_running() Tests


def test_is_tunnel_running_no_pid_file(tunnel_manager):
    """Test is_tunnel_running returns False when no PID file exists."""
    assert tunnel_manager.is_tunnel_running() is False


def test_is_tunnel_running_process_exists(tunnel_manager, mocker):
    """Test is_tunnel_running returns True when process exists."""
    tunnel_manager.tunnel_pid_file.write_text("12345")

    # Mock os.kill to succeed (process exists)
    mock_kill = mocker.patch("gpu_session.ssh.os.kill")

    result = tunnel_manager.is_tunnel_running()

    assert result is True
    # Verify os.kill called with signal 0 (check if process exists)
    mock_kill.assert_called_once_with(12345, 0)


def test_is_tunnel_running_process_not_found(tunnel_manager, mocker):
    """Test is_tunnel_running cleans up stale PID file."""
    tunnel_manager.tunnel_pid_file.write_text("99999")

    # Mock os.kill to raise ProcessLookupError
    mock_kill = mocker.patch("gpu_session.ssh.os.kill")
    mock_kill.side_effect = ProcessLookupError()

    result = tunnel_manager.is_tunnel_running()

    assert result is False
    # Verify stale PID file removed
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_is_tunnel_running_invalid_pid_format(tunnel_manager):
    """Test is_tunnel_running handles invalid PID format."""
    tunnel_manager.tunnel_pid_file.write_text("invalid")

    result = tunnel_manager.is_tunnel_running()

    assert result is False
    # Verify invalid PID file removed
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_is_tunnel_running_empty_pid_file(tunnel_manager):
    """Test is_tunnel_running handles empty PID file."""
    tunnel_manager.tunnel_pid_file.write_text("")

    result = tunnel_manager.is_tunnel_running()

    assert result is False
    assert not tunnel_manager.tunnel_pid_file.exists()


# _find_tunnel_pid() Tests


def test_find_tunnel_pid_success(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid finds PID successfully."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="12345\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid == 12345

    # Verify pgrep command
    call_args = mock_subprocess.call_args[0][0]
    assert call_args[0] == "pgrep"
    assert call_args[1] == "-f"
    assert f"ssh.*{instance_ip}" in call_args[2]


def test_find_tunnel_pid_multiple_pids(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid returns first PID when multiple found."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="12345\n67890\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid == 12345


def test_find_tunnel_pid_no_process_found(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid returns None when no process found."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=1,  # pgrep returns 1 when no match
        stdout="",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_empty_output(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles empty output."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="   \n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_timeout(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles timeout."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = __import__("subprocess").TimeoutExpired(
        cmd="pgrep", timeout=5
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_exception(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles exceptions gracefully."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = OSError("Command not found")

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_invalid_output(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles non-numeric output."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="not-a-number\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


# connect_ssh() Tests


def test_connect_ssh_success(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh opens interactive SSH session successfully."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0)

    result = tunnel_manager.connect_ssh(
        instance_ip=instance_ip,
        username="testuser",
    )

    assert result is True

    # Verify SSH command
    call_args = mock_subprocess.call_args[0][0]
    assert call_args[0] == "ssh"
    assert "-o" in call_args
    assert "StrictHostKeyChecking=no" in call_args
    assert "-i" in call_args
    assert str(tunnel_manager.ssh_key_path) in call_args
    assert f"testuser@{instance_ip}" in call_args

    # Verify subprocess.run called without capture_output (interactive)
    assert "capture_output" not in mock_subprocess.call_args[1]


def test_connect_ssh_default_username(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh uses default username 'ubuntu'."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0)

    tunnel_manager.connect_ssh(instance_ip=instance_ip)

    call_args = mock_subprocess.call_args[0][0]
    assert f"ubuntu@{instance_ip}" in call_args


def test_connect_ssh_failure(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles SSH failure."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=255)

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


def test_connect_ssh_exception(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles exceptions."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = OSError("SSH command not found")

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


def test_connect_ssh_keyboard_interrupt(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles user interrupt."""
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.side_effect = KeyboardInterrupt()

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


# Edge Cases and Integration Tests


def test_start_then_stop_tunnel_integration(tunnel_manager, instance_ip, mocker):
    """Test full start then stop tunnel workflow."""
    # Mock start_tunnel dependencies
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    # Start tunnel
    start_result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )
    assert start_result is True
    assert tunnel_manager.is_tunnel_running() is True

    # Mock stop_tunnel dependencies
    mock_kill = mocker.patch("gpu_session.ssh.os.kill")

    # Stop tunnel
    stop_result = tunnel_manager.stop_tunnel()
    assert stop_result is True
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_multiple_port_forwarding(tunnel_manager, instance_ip, mocker):
    """Test starting tunnel with multiple port forwards."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080, 8888, 9000],
        remote_ports=[80, 443, 3000],
    )

    assert result is True

    # Verify all ports in command
    call_args = mock_subprocess.call_args[0][0]
    assert "8080:localhost:80" in call_args
    assert "8888:localhost:443" in call_args
    assert "9000:localhost:3000" in call_args


def test_ssh_options_in_commands(tunnel_manager, instance_ip, mocker):
    """Test SSH security options are present in commands."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("gpu_session.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    call_args = mock_subprocess.call_args[0][0]
    assert "StrictHostKeyChecking=no" in call_args
    assert "UserKnownHostsFile=/dev/null" in call_args
    assert "ServerAliveInterval=60" in call_args


def test_tunnel_manager_with_tilde_path():
    """Test SSHTunnelManager expands tilde in SSH key path."""
    manager = SSHTunnelManager("~/custom/path/key.pem")
    expected_path = Path.home() / "custom" / "path" / "key.pem"
    assert manager.ssh_key_path == expected_path
