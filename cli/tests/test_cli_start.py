"""Tests for 'gpu-session start' cost confirmation."""

import pytest
from unittest.mock import Mock
from rich.console import Console
from io import StringIO
from soong.lambda_api import InstanceType


def test_show_cost_estimate_displays_all_info(mocker):
    """Test show_cost_estimate displays GPU, rate, duration, and cost."""
    from soong.cli import show_cost_estimate

    # Capture console output
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)

    # Patch the module console
    mocker.patch("soong.cli.console", test_console)

    # Create mock instance type
    instance_type = Mock(spec=InstanceType)
    instance_type.description = "1x A100 SXM4 (80 GB)"
    instance_type.format_price.return_value = "$1.29/hr"
    instance_type.estimate_cost.return_value = 5.16

    # Mock questionary to return True (proceed)
    mocker.patch("questionary.confirm", return_value=Mock(ask=lambda: True))

    # Call the function
    result = show_cost_estimate(instance_type, hours=4, action="launch")

    # Verify it returned True
    assert result is True

    # Verify output contains all required information
    result_output = output.getvalue()
    assert "Cost Estimate" in result_output
    assert "1x A100 SXM4" in result_output or "A100" in result_output
    assert "1.29" in result_output  # Rate
    assert "4" in result_output  # Duration
    assert "5.16" in result_output  # Estimated cost
    assert "Proceed" in result_output or "Launch" in result_output or "launch" in result_output


def test_show_cost_estimate_returns_false_when_cancelled(mocker):
    """Test show_cost_estimate returns False when user cancels."""
    from soong.cli import show_cost_estimate

    # Capture console output
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)

    mocker.patch("soong.cli.console", test_console)

    # Create mock instance type
    instance_type = Mock(spec=InstanceType)
    instance_type.description = "1x A6000 (48 GB)"
    instance_type.format_price.return_value = "$0.80/hr"
    instance_type.estimate_cost.return_value = 3.20

    # Mock questionary to return False (cancel)
    mocker.patch("questionary.confirm", return_value=Mock(ask=lambda: False))

    # Call the function
    result = show_cost_estimate(instance_type, hours=4, action="launch")

    # Verify it returned False
    assert result is False


def test_start_command_shows_cost_confirmation(mocker, sample_config):
    """Test 'gpu-session start' shows cost confirmation before launch."""
    from typer.testing import CliRunner
    from soong.cli import app

    runner = CliRunner()

    # Mock config manager
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock Lambda API
    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    # Create mock instance type
    instance_type_mock = Mock(spec=InstanceType)
    instance_type_mock.name = "gpu_1x_a100_sxm4_80gb"
    instance_type_mock.description = "1x A100 SXM4 (80 GB)"
    instance_type_mock.price_per_hour = 1.29
    instance_type_mock.format_price.return_value = "$1.29/hr"
    instance_type_mock.estimate_cost.return_value = 5.16

    mock_api.get_instance_type.return_value = instance_type_mock
    mock_api.list_ssh_keys.return_value = ["test-key"]

    # Mock questionary to cancel (return False)
    mocker.patch("questionary.confirm", return_value=Mock(ask=lambda: False))

    # Run start command
    result = runner.invoke(app, ["start"], catch_exceptions=False)

    # Verify cost estimate was shown
    assert "Cost Estimate" in result.stdout or "Estimated cost" in result.stdout
    assert "5.16" in result.stdout  # 4 hours * $1.29
    assert "cancelled" in result.stdout.lower() or "Launch cancelled" in result.stdout


def test_start_command_with_yes_flag_skips_confirmation(mocker, sample_config):
    """Test 'gpu-session start -y' skips cost confirmation."""
    from typer.testing import CliRunner
    from soong.cli import app

    runner = CliRunner()

    # Mock config manager
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock Lambda API
    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value
    mock_api.get_instance_type.return_value = None  # No pricing available
    mock_api.list_ssh_keys.return_value = ["test-key"]
    mock_api.launch_instance.return_value = "i-12345"

    # Mock instance manager
    mock_mgr_class = mocker.patch("soong.cli.InstanceManager")
    mock_mgr = mock_mgr_class.return_value
    mock_mgr.wait_for_ready.return_value = None  # Timeout (doesn't matter for this test)

    # Mock questionary - should NOT be called when -y flag is used
    mock_confirm = mocker.patch("questionary.confirm")

    # Run start command with -y flag
    result = runner.invoke(app, ["start", "-y"], catch_exceptions=False)

    # Verify questionary.confirm was NOT called (cost confirmation was skipped)
    mock_confirm.assert_not_called()

    # Verify instance was launched
    assert "Launching instance" in result.stdout or "launched" in result.stdout.lower()


def test_start_command_format_matches_requirement(mocker, sample_config):
    """Test cost confirmation shows: GPU, Rate, Duration, Estimated Cost, Prompt."""
    from typer.testing import CliRunner
    from soong.cli import app

    runner = CliRunner()

    # Mock config manager
    mock_manager = mocker.patch("soong.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock Lambda API
    mock_api_class = mocker.patch("soong.cli.LambdaAPI")
    mock_api = mock_api_class.return_value

    instance_type_mock = Mock(spec=InstanceType)
    instance_type_mock.description = "1x A100 SXM4 (80 GB)"
    instance_type_mock.format_price.return_value = "$1.29/hr"
    instance_type_mock.estimate_cost.return_value = 5.16

    mock_api.get_instance_type.return_value = instance_type_mock
    mock_api.list_ssh_keys.return_value = ["test-key"]

    # Mock questionary to proceed
    mocker.patch("questionary.confirm", return_value=Mock(ask=lambda: True))

    # Mock instance launch
    mock_api.launch_instance.return_value = "i-test-123"
    mock_mgr_class = mocker.patch("soong.cli.InstanceManager")
    mock_mgr_class.return_value.wait_for_ready.return_value = Mock(ip="1.2.3.4")

    # Run start command
    result = runner.invoke(app, ["start"], catch_exceptions=False)

    # Verify all required fields are present:
    # 1. GPU: instance_type.description
    assert "A100" in result.stdout

    # 2. Rate: instance_type.format_price()
    assert "1.29" in result.stdout

    # 3. Duration: hours
    assert "4" in result.stdout

    # 4. Estimated Cost: estimate_cost result
    assert "5.16" in result.stdout

    # 5. Prompt asking to proceed
    # (This is handled by questionary.confirm, which we've mocked)
