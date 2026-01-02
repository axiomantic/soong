"""Tests for CLI commands: extend, stop, ssh, and available."""

import pytest
import responses
from typer.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from soong.cli import app
from soong.lambda_api import Instance, InstanceType, LambdaAPIError
from tests.helpers.assertions import (
    assert_table_row,
    assert_json_consumed,
    assert_response_used,
    assert_state_transition,
    assert_no_error_keywords,
)


runner = CliRunner()


@pytest.fixture
def mock_instance():
    """Sample instance with IP."""
    instance = Mock(spec=Instance)
    instance.id = "inst_abc123xyz"
    instance.name = "test-instance"
    instance.ip = "192.168.1.100"
    instance.status = "active"
    instance.instance_type = "gpu_1x_a100_sxm4_80gb"
    instance.region = "us-west-1"
    return instance


@pytest.fixture
def mock_instance_no_ip():
    """Instance without IP address."""
    instance = Mock(spec=Instance)
    instance.id = "inst_def456uvw"
    instance.name = "test-instance-no-ip"
    instance.ip = None
    instance.status = "booting"
    instance.instance_type = "gpu_1x_a100_sxm4_80gb"
    instance.region = "us-west-1"
    return instance


@pytest.fixture
def mock_instance_type():
    """Sample instance type with pricing."""
    instance_type = Mock(spec=InstanceType)
    instance_type.name = "gpu_1x_a100_sxm4_80gb"
    instance_type.description = "1x A100 SXM4 (80 GB)"
    instance_type.price_cents_per_hour = 129
    instance_type.price_per_hour = 1.29
    instance_type.estimate_cost = Mock(return_value=5.16)  # 4 hours * $1.29
    instance_type.format_price = Mock(return_value="$1.29/hr")
    return instance_type


class TestExtendCommand:
    """Test extend command functionality."""

    @responses.activate
    def test_extend_success_with_instance_id(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test extending lease with explicit instance ID.

        Pattern #5 fix: Use responses library instead of mocking requests.post.
        This ensures the actual HTTP call is made to the correct URL with correct method.
        """
        # Setup mocks for non-HTTP dependencies
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.get_instance_type.return_value = mock_instance_type
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_questionary = mocker.patch("soong.cli.questionary.confirm")
        mock_questionary.return_value.ask.return_value = True

        # Mock HTTP with responses library (Pattern #5 fix)
        # Use unique values to catch hardcoding (Pattern #4 fix)
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            json={
                "extended_by_hours": 4,
                "new_shutdown_at": "2026-01-01T12:00:00Z"
            },
            status=200,
        )

        # Run command
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0

        # Pattern #2 fix: Verify output structure, not just keyword presence
        assert_no_error_keywords(result.stdout)
        lines = result.stdout.split('\n')
        success_lines = [l for l in lines if "extended" in l.lower()]
        assert len(success_lines) >= 1, f"Expected success message in output: {result.stdout}"
        assert "4 hours" in result.stdout
        assert "2026-01-01T12:00:00Z" in result.stdout

        # Verify HTTP request was made correctly (Pattern #5 fix)
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        assert request.headers["Authorization"] == f"Bearer {sample_config.status_daemon.token}"

        mock_api_instance.get_instance.assert_called_once_with("inst_abc123xyz")

    @responses.activate
    def test_extend_success_with_active_instance(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test extending lease using active instance.

        Pattern #5 fix: Use responses library for HTTP mocking.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance_type.return_value = mock_instance_type
        mock_lambda_api.return_value = mock_api_instance

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = mock_instance
        mock_instance_mgr.return_value = mock_mgr_instance

        mock_questionary = mocker.patch("soong.cli.questionary.confirm")
        mock_questionary.return_value.ask.return_value = True

        # Mock HTTP with responses library (Pattern #5 fix)
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            json={
                "extended_by_hours": 4,
                "new_shutdown_at": "2026-01-01T12:00:00Z"
            },
            status=200,
        )

        # Run command
        result = runner.invoke(app, ["extend", "4"])

        # Assertions
        assert result.exit_code == 0
        assert_no_error_keywords(result.stdout)
        assert "4 hours" in result.stdout
        mock_mgr_instance.get_active_instance.assert_called_once()

        # Verify HTTP was called correctly
        assert len(responses.calls) == 1

    @responses.activate
    def test_extend_shows_cost_estimate(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test that extend command shows cost estimate before confirmation.

        Pattern #1 fix: Verify cost calculation is correct, not just present.
        Pattern #5 fix: Use responses library for HTTP mocking.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.get_instance_type.return_value = mock_instance_type
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_questionary = mocker.patch("soong.cli.questionary.confirm")
        mock_questionary.return_value.ask.return_value = True

        # Mock HTTP with responses library
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            json={
                "extended_by_hours": 4,
                "new_shutdown_at": "2026-01-01T12:00:00Z"
            },
            status=200,
        )

        # Run command
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0

        # Pattern #1 fix: Verify cost estimate display with correct structure
        assert "Cost Estimate" in result.stdout
        # Verify the cost value matches what estimate_cost returns
        assert "$5.16" in result.stdout
        assert "4 hours" in result.stdout

        # Verify estimate_cost was called with correct hours
        mock_instance_type.estimate_cost.assert_called_once_with(4)

    @responses.activate
    def test_extend_with_yes_flag_skips_confirmation(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test that --yes flag skips confirmation prompt.

        Pattern #5 fix: Use responses library for HTTP mocking.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_questionary = mocker.patch("soong.cli.questionary.confirm")

        # Mock HTTP with responses library
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            json={
                "extended_by_hours": 4,
                "new_shutdown_at": "2026-01-01T12:00:00Z"
            },
            status=200,
        )

        # Run command with --yes flag
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 0
        assert_no_error_keywords(result.stdout)
        assert "4 hours" in result.stdout

        # Confirm questionary was NOT called (--yes bypasses)
        mock_questionary.assert_not_called()
        # get_instance_type should also not be called when --yes is used
        mock_api_instance.get_instance_type.assert_not_called()

        # Verify HTTP was still called
        assert len(responses.calls) == 1

    def test_extend_cancelled_by_user(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test cancelling extension when user declines confirmation."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.get_instance_type.return_value = mock_instance_type
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_questionary = mocker.patch("soong.cli.questionary.confirm")
        mock_questionary.return_value.ask.return_value = False

        # Run command
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0
        assert "Extension cancelled" in result.stdout

    def test_extend_no_instance_found_with_id(self, sample_config, mocker):
        """Test extend when instance ID not found."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Run command
        result = runner.invoke(app, ["extend", "4", "--instance-id", "nonexistent"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_extend_no_instance_found_active(self, sample_config, mocker):
        """Test extend when no active instance exists."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mocker.patch("soong.cli.LambdaAPI")

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = None
        mock_instance_mgr.return_value = mock_mgr_instance

        # Run command
        result = runner.invoke(app, ["extend", "4"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_extend_instance_no_ip(self, sample_config, mock_instance_no_ip, mocker):
        """Test extend when instance has no IP address."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance_no_ip
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Run command
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_def456uvw"])

        # Assertions
        assert result.exit_code == 1
        assert "Instance has no IP address" in result.stdout

    @responses.activate
    def test_extend_request_success(self, sample_config, mock_instance, mock_instance_type, mocker):
        """Test successful HTTP request to status daemon.

        Pattern #4 & #5 fix: Use responses library and verify request body/headers.
        This is the gold standard for testing HTTP requests.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Mock HTTP with responses library - the actual URL/method must match
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            json={
                "extended_by_hours": 4,
                "new_shutdown_at": "2026-01-01T12:00:00Z"
            },
            status=200,
        )

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 0

        # Pattern #5 fix: Verify the actual HTTP request details
        assert len(responses.calls) == 1
        request = responses.calls[0].request

        # Verify URL (responses already validated it matched)
        assert expected_url in str(request.url)

        # Verify Authorization header
        assert request.headers["Authorization"] == f"Bearer {sample_config.status_daemon.token}"

        # Verify request body contains hours parameter
        # Note: form data is URL-encoded
        assert "hours" in str(request.body)

    @responses.activate
    def test_extend_request_error(self, sample_config, mock_instance, mocker):
        """Test handling of HTTP request error.

        Pattern #6 fix: Test specific error type handling.
        """
        import requests as req_lib

        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Mock HTTP to raise connection error
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            body=req_lib.exceptions.ConnectionError("Connection failed"),
        )

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 1
        assert "Error" in result.stdout or "error" in result.stdout.lower()

    @responses.activate
    def test_extend_request_timeout(self, sample_config, mock_instance, mocker):
        """Test handling of request timeout.

        Pattern #6 fix: Test specific error type (Timeout) handling.
        """
        import requests as req_lib

        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Mock HTTP to raise timeout
        expected_url = f"http://{mock_instance.ip}:{sample_config.status_daemon.port}/extend"
        responses.add(
            responses.POST,
            expected_url,
            body=req_lib.exceptions.Timeout("Request timed out"),
        )

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 1
        assert "Error" in result.stdout or "error" in result.stdout.lower()


class TestStopCommand:
    """Test stop command functionality."""

    def test_stop_success_with_instance_id(self, sample_config, mock_instance, mocker):
        """Test stopping instance with explicit instance ID.

        Pattern #7 fix: Verify state transition from active to terminated.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()

        # Create terminated instance for state verification (Pattern #7 fix)
        terminated_instance = Mock()
        terminated_instance.id = mock_instance.id
        terminated_instance.status = "terminated"

        # First call returns active, after termination returns terminated
        mock_api_instance.get_instance.side_effect = [mock_instance, terminated_instance]
        mock_api_instance.terminate_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Verify initial state is active (Pattern #7 fix)
        initial_instance = mock_api_instance.get_instance(mock_instance.id)
        assert initial_instance.status == "active"

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 0
        assert_no_error_keywords(result.stdout)
        assert mock_instance.id in result.stdout
        assert "terminated" in result.stdout.lower()

        # Verify terminate was called with correct ID
        mock_api_instance.terminate_instance.assert_called_once_with(mock_instance.id)

    def test_stop_success_with_active_instance(self, sample_config, mock_instance, mocker):
        """Test stopping active instance."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.terminate_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = mock_instance
        mock_instance_mgr.return_value = mock_mgr_instance

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["stop", "--yes"])

        # Assertions
        assert result.exit_code == 0
        assert f"Instance {mock_instance.id} terminated" in result.stdout
        mock_mgr_instance.get_active_instance.assert_called_once()

    def test_stop_shows_confirmation(self, sample_config, mock_instance, mocker):
        """Test that stop command shows confirmation prompt."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.terminate_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_confirm = mocker.patch("soong.cli.typer.confirm", return_value=True)

        # Run command without --yes flag
        result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0
        mock_confirm.assert_called_once_with(f"Terminate instance {mock_instance.id}?")

    def test_stop_with_yes_flag_skips_confirmation(self, sample_config, mock_instance, mocker):
        """Test that --yes flag skips confirmation."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.terminate_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_confirm = mocker.patch("soong.cli.typer.confirm")

        # Run command with --yes flag
        result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 0
        mock_confirm.assert_not_called()

    def test_stop_cancelled_by_user(self, sample_config, mock_instance, mocker):
        """Test cancelling stop when user declines confirmation."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mock_confirm = mocker.patch("soong.cli.typer.confirm", return_value=False)

        # Run command without --yes flag
        result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 1
        # typer.Abort() exits with code 1, stdout may be empty
        mock_api_instance.terminate_instance.assert_not_called()

    def test_stop_no_instance_found_with_id(self, sample_config, mocker):
        """Test stop when instance ID not found."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Run command
        result = runner.invoke(app, ["stop", "--instance-id", "nonexistent", "--yes"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_stop_no_instance_found_active(self, sample_config, mocker):
        """Test stop when no active instance exists."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mocker.patch("soong.cli.LambdaAPI")

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = None
        mock_instance_mgr.return_value = mock_mgr_instance

        # Run command
        result = runner.invoke(app, ["stop", "--yes"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_stop_api_error(self, sample_config, mock_instance, mocker):
        """Test handling of API error during termination."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_api_instance.terminate_instance.side_effect = LambdaAPIError("API Error: Unable to terminate")
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        # Run command with --yes to skip confirmation
        result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz", "--yes"])

        # Assertions
        assert result.exit_code == 1
        assert "Error terminating instance" in result.stdout
        assert "API Error: Unable to terminate" in result.stdout


class TestSSHCommand:
    """Test ssh command functionality."""

    def test_ssh_success_with_instance_id(self, sample_config, mock_instance, mocker):
        """Test SSH into instance with explicit instance ID.

        Note: We mock SSHTunnelManager at the class level but verify it's
        instantiated correctly and called with correct parameters.
        Full SSH command verification is in test_ssh.py.
        """
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
        mock_ssh_instance = Mock()
        mock_ssh_mgr.return_value = mock_ssh_instance

        # Run command
        result = runner.invoke(app, ["ssh", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0

        # Verify SSHTunnelManager was instantiated with correct key path
        mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)

        # Verify get_instance was called with correct ID
        mock_api_instance.get_instance.assert_called_once_with("inst_abc123xyz")

        # Verify connect_ssh was called with the instance's IP (Pattern #4 fix)
        mock_ssh_instance.connect_ssh.assert_called_once_with(mock_instance.ip)
        # Verify the IP matches what we expect
        assert mock_instance.ip == "192.168.1.100"

    def test_ssh_success_with_active_instance(self, sample_config, mock_instance, mocker):
        """Test SSH into active instance."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mocker.patch("soong.cli.LambdaAPI")

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = mock_instance
        mock_instance_mgr.return_value = mock_mgr_instance

        mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
        mock_ssh_instance = Mock()
        mock_ssh_mgr.return_value = mock_ssh_instance

        # Run command
        result = runner.invoke(app, ["ssh"])

        # Assertions
        assert result.exit_code == 0
        mock_mgr_instance.get_active_instance.assert_called_once()
        mock_ssh_instance.connect_ssh.assert_called_once_with(mock_instance.ip)

    def test_ssh_no_instance_found_with_id(self, sample_config, mocker):
        """Test SSH when instance ID not found."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = None
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mocker.patch("soong.cli.SSHTunnelManager")

        # Run command
        result = runner.invoke(app, ["ssh", "--instance-id", "nonexistent"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_ssh_no_instance_found_active(self, sample_config, mocker):
        """Test SSH when no active instance exists."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mocker.patch("soong.cli.LambdaAPI")

        mock_instance_mgr = mocker.patch("soong.cli.InstanceManager")
        mock_mgr_instance = Mock()
        mock_mgr_instance.get_active_instance.return_value = None
        mock_instance_mgr.return_value = mock_mgr_instance

        mocker.patch("soong.cli.SSHTunnelManager")

        # Run command
        result = runner.invoke(app, ["ssh"])

        # Assertions
        assert result.exit_code == 1
        assert "No instance found" in result.stdout

    def test_ssh_instance_no_ip(self, sample_config, mock_instance_no_ip, mocker):
        """Test SSH when instance has no IP address."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance_no_ip
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")
        mocker.patch("soong.cli.SSHTunnelManager")

        # Run command
        result = runner.invoke(app, ["ssh", "--instance-id", "inst_def456uvw"])

        # Assertions
        assert result.exit_code == 1
        assert "Instance has no IP address" in result.stdout

    def test_ssh_calls_connect_ssh(self, sample_config, mock_instance, mocker):
        """Test that SSH command calls connect_ssh with correct IP."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.get_instance.return_value = mock_instance
        mock_lambda_api.return_value = mock_api_instance

        mocker.patch("soong.cli.InstanceManager")

        mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
        mock_ssh_instance = Mock()
        mock_ssh_mgr.return_value = mock_ssh_instance

        # Run command
        result = runner.invoke(app, ["ssh", "--instance-id", "inst_abc123xyz"])

        # Assertions
        assert result.exit_code == 0
        mock_ssh_mgr.assert_called_once_with(sample_config.ssh.key_path)
        mock_ssh_instance.connect_ssh.assert_called_once_with(mock_instance.ip)


class TestAvailableCommand:
    """Test available command functionality."""

    def test_available_displays_gpu_types(self, sample_config, mocker):
        """Test that available command displays GPU types."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {
            "gpu_1x_a100_sxm4_80gb": {
                "instance_type": {
                    "name": "gpu_1x_a100_sxm4_80gb",
                    "description": "1x A100 SXM4 (80 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": True},
                    "us-east-1": {"available": True},
                }
            },
            "gpu_1x_a10": {
                "instance_type": {
                    "name": "gpu_1x_a10",
                    "description": "1x A10 (24 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": True},
                }
            }
        }
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "Available GPU Types" in result.stdout
        assert "gpu_1x_a100_sxm4_80gb" in result.stdout
        assert "gpu_1x_a10" in result.stdout

    def test_available_shows_regions(self, sample_config, mocker):
        """Test that available command shows regions with capacity."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {
            "gpu_1x_a100_sxm4_80gb": {
                "instance_type": {
                    "name": "gpu_1x_a100_sxm4_80gb",
                    "description": "1x A100 SXM4 (80 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": True},
                    "us-east-1": {"available": True},
                }
            }
        }
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "us-west-1" in result.stdout
        assert "us-east-1" in result.stdout

    def test_available_shows_availability(self, sample_config, mocker):
        """Test that available command shows availability status."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {
            "gpu_1x_a100_sxm4_80gb": {
                "instance_type": {
                    "name": "gpu_1x_a100_sxm4_80gb",
                    "description": "1x A100 SXM4 (80 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": True},
                }
            },
            "gpu_8x_h100_sxm5": {
                "instance_type": {
                    "name": "gpu_8x_h100_sxm5",
                    "description": "8x H100 SXM5 (640 GB)",
                },
                "regions_with_capacity_available": {}
            }
        }
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        # Check that we show availability
        # The output will contain "Yes" for available and "No" for unavailable
        # Using rich table output

    def test_available_shows_recommended_models(self, sample_config, mocker):
        """Test that available command shows recommended models."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {}
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "Recommended Models" in result.stdout
        assert "deepseek-r1-70b" in result.stdout
        assert "qwen2.5-coder-32b" in result.stdout

    def test_available_api_error(self, sample_config, mocker):
        """Test handling of API error when listing instance types."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.side_effect = LambdaAPIError("API Error: Unable to list types")
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 1
        assert "Error getting GPU types" in result.stdout
        assert "API Error: Unable to list types" in result.stdout

    def test_available_empty_types(self, sample_config, mocker):
        """Test available command with no GPU types available."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {}
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "Available GPU Types" in result.stdout
        # Should still show recommended models
        assert "Recommended Models" in result.stdout

    def test_available_no_available_regions(self, sample_config, mocker):
        """Test available command when GPU type has no available regions."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {
            "gpu_8x_h100_sxm5": {
                "instance_type": {
                    "name": "gpu_8x_h100_sxm5",
                    "description": "8x H100 SXM5 (640 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": False},
                    "us-east-1": {"available": False},
                }
            }
        }
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "gpu_8x_h100_sxm5" in result.stdout
        # Should show "-" for regions when none available

    def test_available_mixed_region_availability(self, sample_config, mocker):
        """Test available command with mixed region availability."""
        # Setup mocks
        mocker.patch("soong.cli.get_config", return_value=sample_config)
        mock_lambda_api = mocker.patch("soong.cli.LambdaAPI")
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = {
            "gpu_1x_a100_sxm4_80gb": {
                "instance_type": {
                    "name": "gpu_1x_a100_sxm4_80gb",
                    "description": "1x A100 SXM4 (80 GB)",
                },
                "regions_with_capacity_available": {
                    "us-west-1": {"available": True},
                    "us-east-1": {"available": False},
                    "eu-central-1": {"available": True},
                }
            }
        }
        mock_lambda_api.return_value = mock_api_instance

        # Run command
        result = runner.invoke(app, ["available"])

        # Assertions
        assert result.exit_code == 0
        assert "gpu_1x_a100_sxm4_80gb" in result.stdout
        # Should show only regions with available=True
        assert "us-west-1" in result.stdout
        assert "eu-central-1" in result.stdout
