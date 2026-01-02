"""Tests for ssh.py SSH tunnel management."""

import pytest
import signal
from pathlib import Path
from unittest.mock import Mock, MagicMock
from soong.ssh import SSHTunnelManager
from tests.helpers.assertions import assert_exact_command, assert_ssh_command


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
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")

    # Use unique PID to prove consumption (Pattern #4 fix)
    unique_pid = 99887
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=unique_pid)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080, 8888],
        remote_ports=[80, 443],
        username="testuser",
    )

    # Verify result
    assert result is True

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify SSH command built correctly (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-N",
        "-f",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=60",
        "-i", str(tunnel_manager.ssh_key_path),
        "-L", "8080:localhost:80",
        "-L", "8888:localhost:443",
        f"testuser@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)

    # Verify PID file created with consumed value (Pattern #4 fix)
    assert tunnel_manager.tunnel_pid_file.exists()
    pid_from_file = tunnel_manager.tunnel_pid_file.read_text()
    assert pid_from_file == str(unique_pid), (
        f"PID file should contain {unique_pid} from mock, got {pid_from_file}"
    )


def test_start_tunnel_success_without_pid(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel succeeds even if PID not found."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=None)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    assert result is True
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_start_tunnel_ssh_command_failed(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel handles SSH command failure."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=255,
        stderr="Permission denied (publickey)."
    )

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    assert result is False


def test_start_tunnel_timeout(tunnel_manager, instance_ip, mocker):
    """Test start_tunnel handles timeout."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
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
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
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
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify exact command structure (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-N",
        "-f",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=60",
        "-i", str(tunnel_manager.ssh_key_path),
        "-L", "8080:localhost:80",
        f"ubuntu@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)


def test_start_tunnel_creates_pid_file_directory(tunnel_manager, instance_ip, mocker, tmp_path):
    """Test start_tunnel creates PID file directory if missing."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
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
    # Use unique PID to prove consumption (Pattern #4 fix)
    unique_pid = 77889
    tunnel_manager.tunnel_pid_file.write_text(str(unique_pid))

    # Mock os.kill
    mock_kill = mocker.patch("soong.ssh.os.kill")

    result = tunnel_manager.stop_tunnel()

    # Verify result
    assert result is True

    # Verify os.kill called with correct PID (Pattern #4 fix)
    mock_kill.assert_called_once_with(unique_pid, signal.SIGTERM)

    # Verify the PID from file was actually used
    call_args = mock_kill.call_args[0]
    assert call_args[0] == unique_pid, (
        f"Should have used PID {unique_pid} from file, got {call_args[0]}"
    )

    # Verify PID file removed
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_stop_tunnel_process_not_found(tunnel_manager, mocker):
    """Test stop_tunnel handles ProcessLookupError (stale PID)."""
    tunnel_manager.tunnel_pid_file.write_text("99999")

    # Mock os.kill to raise ProcessLookupError
    mock_kill = mocker.patch("soong.ssh.os.kill")
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

    mock_kill = mocker.patch("soong.ssh.os.kill")
    mock_kill.side_effect = PermissionError("Operation not permitted")

    result = tunnel_manager.stop_tunnel()

    assert result is False
    # PID file should not be removed on error
    assert tunnel_manager.tunnel_pid_file.exists()


def test_stop_tunnel_whitespace_in_pid(tunnel_manager, mocker):
    """Test stop_tunnel handles whitespace in PID file."""
    tunnel_manager.tunnel_pid_file.write_text("  12345  \n")

    mock_kill = mocker.patch("soong.ssh.os.kill")

    result = tunnel_manager.stop_tunnel()

    assert result is True
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)


# is_tunnel_running() Tests


def test_is_tunnel_running_no_pid_file(tunnel_manager):
    """Test is_tunnel_running returns False when no PID file exists."""
    assert tunnel_manager.is_tunnel_running() is False


def test_is_tunnel_running_process_exists(tunnel_manager, mocker):
    """Test is_tunnel_running returns True when process exists."""
    # Use unique PID to prove consumption (Pattern #4 fix)
    unique_pid = 55443
    tunnel_manager.tunnel_pid_file.write_text(str(unique_pid))

    # Mock os.kill to succeed (process exists)
    mock_kill = mocker.patch("soong.ssh.os.kill")

    result = tunnel_manager.is_tunnel_running()

    assert result is True

    # Verify os.kill called with correct PID from file (Pattern #4 fix)
    mock_kill.assert_called_once_with(unique_pid, 0)

    # Verify the PID from file was actually used
    call_args = mock_kill.call_args[0]
    assert call_args[0] == unique_pid, (
        f"Should check PID {unique_pid} from file, got {call_args[0]}"
    )


def test_is_tunnel_running_process_not_found(tunnel_manager, mocker):
    """Test is_tunnel_running cleans up stale PID file."""
    tunnel_manager.tunnel_pid_file.write_text("99999")

    # Mock os.kill to raise ProcessLookupError
    mock_kill = mocker.patch("soong.ssh.os.kill")
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
    # Use unique PID to prove consumption (Pattern #4 fix)
    unique_pid = 88776
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout=f"{unique_pid}\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify returned PID matches mock output (Pattern #4 fix)
    assert pid == unique_pid, (
        f"Should return PID {unique_pid} from subprocess output, got {pid}"
    )

    # Verify pgrep command (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = ["pgrep", "-f", f"ssh.*{instance_ip}"]
    assert_exact_command(call_args, expected_cmd)


def test_find_tunnel_pid_multiple_pids(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid returns first PID when multiple found."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="12345\n67890\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid == 12345


def test_find_tunnel_pid_no_process_found(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid returns None when no process found."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=1,  # pgrep returns 1 when no match
        stdout="",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_empty_output(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles empty output."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="   \n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_timeout(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles timeout."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.side_effect = __import__("subprocess").TimeoutExpired(
        cmd="pgrep", timeout=5
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_exception(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles exceptions gracefully."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.side_effect = OSError("Command not found")

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


def test_find_tunnel_pid_invalid_output(tunnel_manager, instance_ip, mocker):
    """Test _find_tunnel_pid handles non-numeric output."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout="not-a-number\n",
    )

    pid = tunnel_manager._find_tunnel_pid(instance_ip)

    assert pid is None


# connect_ssh() Tests


def test_connect_ssh_success(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh opens interactive SSH session successfully."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0)

    result = tunnel_manager.connect_ssh(
        instance_ip=instance_ip,
        username="testuser",
    )

    assert result is True

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify SSH command (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-i", str(tunnel_manager.ssh_key_path),
        f"testuser@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)

    # Verify subprocess.run called without capture_output (interactive)
    assert "capture_output" not in mock_subprocess.call_args[1]


def test_connect_ssh_default_username(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh uses default username 'ubuntu'."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0)

    tunnel_manager.connect_ssh(instance_ip=instance_ip)

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify exact command with default username (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-i", str(tunnel_manager.ssh_key_path),
        f"ubuntu@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)


def test_connect_ssh_failure(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles SSH failure."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=255)

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


def test_connect_ssh_exception(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles exceptions."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.side_effect = OSError("SSH command not found")

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


def test_connect_ssh_keyboard_interrupt(tunnel_manager, instance_ip, mocker):
    """Test connect_ssh handles user interrupt."""
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.side_effect = KeyboardInterrupt()

    result = tunnel_manager.connect_ssh(instance_ip=instance_ip)

    assert result is False


# Edge Cases and Integration Tests


def test_start_then_stop_tunnel_integration(tunnel_manager, instance_ip, mocker):
    """Test full start then stop tunnel workflow."""
    # Mock start_tunnel dependencies
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    unique_pid = 54321
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=unique_pid)

    # Start tunnel
    start_result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )
    assert start_result is True

    # Mock os.kill for is_tunnel_running check
    mock_kill = mocker.patch("soong.ssh.os.kill")

    # Verify tunnel is running
    assert tunnel_manager.is_tunnel_running() is True
    mock_kill.assert_called_once_with(unique_pid, 0)

    # Reset mock for stop_tunnel
    mock_kill.reset_mock()

    # Stop tunnel
    stop_result = tunnel_manager.stop_tunnel()
    assert stop_result is True
    mock_kill.assert_called_once_with(unique_pid, signal.SIGTERM)
    assert not tunnel_manager.tunnel_pid_file.exists()


def test_multiple_port_forwarding(tunnel_manager, instance_ip, mocker):
    """Test starting tunnel with multiple port forwards."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    result = tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080, 8888, 9000],
        remote_ports=[80, 443, 3000],
    )

    assert result is True

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify all ports in command (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-N",
        "-f",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=60",
        "-i", str(tunnel_manager.ssh_key_path),
        "-L", "8080:localhost:80",
        "-L", "8888:localhost:443",
        "-L", "9000:localhost:3000",
        f"ubuntu@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)


def test_ssh_options_in_commands(tunnel_manager, instance_ip, mocker):
    """Test SSH security options are present in commands."""
    mocker.patch.object(tunnel_manager, "is_tunnel_running", return_value=False)
    mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
    mock_subprocess.return_value = Mock(returncode=0, stderr="")
    mocker.patch.object(tunnel_manager, "_find_tunnel_pid", return_value=12345)

    tunnel_manager.start_tunnel(
        instance_ip=instance_ip,
        local_ports=[8080],
        remote_ports=[80],
    )

    # Verify subprocess was called (Pattern #4 fix)
    mock_subprocess.assert_called_once()

    # Verify exact command with security options (Pattern #2 & #5 fix)
    call_args = mock_subprocess.call_args[0][0]
    expected_cmd = [
        "ssh",
        "-N",
        "-f",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=60",
        "-i", str(tunnel_manager.ssh_key_path),
        "-L", "8080:localhost:80",
        f"ubuntu@{instance_ip}"
    ]
    assert_exact_command(call_args, expected_cmd)


def test_tunnel_manager_with_tilde_path():
    """Test SSHTunnelManager expands tilde in SSH key path."""
    manager = SSHTunnelManager("~/custom/path/key.pem")
    expected_path = Path.home() / "custom" / "path" / "key.pem"
    assert manager.ssh_key_path == expected_path
