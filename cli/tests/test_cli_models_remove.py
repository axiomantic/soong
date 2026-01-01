"""Tests for 'gpu-session models remove' command."""

import pytest
from typer.testing import CliRunner
from gpu_session.cli import app
from gpu_session.config import Config, LambdaConfig, StatusDaemonConfig


runner = CliRunner()


def test_models_remove_custom_model_with_confirmation(mocker, temp_config_dir, custom_model_dict):
    """Test 'gpu-session models remove' removes custom model after confirmation."""
    # Setup config with custom model
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={"my-custom-model": custom_model_dict},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    # Mock confirmation as "yes"
    mocker.patch("questionary.confirm", return_value=mocker.Mock(ask=lambda: True))

    result = runner.invoke(app, ["models", "remove", "my-custom-model"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "my-custom-model" in result.stdout.lower()
    assert "removed" in result.stdout.lower()

    # Verify save was called with updated config
    mock_manager.save.assert_called_once()
    saved_config = mock_manager.save.call_args[0][0]
    assert "my-custom-model" not in saved_config.custom_models


def test_models_remove_custom_model_with_yes_flag(mocker, temp_config_dir, custom_model_dict):
    """Test 'gpu-session models remove --yes' skips confirmation."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={"my-custom-model": custom_model_dict},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    # Should not prompt for confirmation
    mock_confirm = mocker.patch("questionary.confirm")

    result = runner.invoke(app, ["models", "remove", "my-custom-model", "--yes"], catch_exceptions=False)

    assert result.exit_code == 0
    mock_confirm.assert_not_called()

    # Verify model was removed
    mock_manager.save.assert_called_once()
    saved_config = mock_manager.save.call_args[0][0]
    assert "my-custom-model" not in saved_config.custom_models


def test_models_remove_custom_model_with_y_flag(mocker, temp_config_dir, custom_model_dict):
    """Test 'gpu-session models remove -y' short flag works."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={"my-custom-model": custom_model_dict},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    result = runner.invoke(app, ["models", "remove", "my-custom-model", "-y"], catch_exceptions=False)

    assert result.exit_code == 0

    # Verify model was removed
    mock_manager.save.assert_called_once()
    saved_config = mock_manager.save.call_args[0][0]
    assert "my-custom-model" not in saved_config.custom_models


def test_models_remove_cancel_confirmation(mocker, temp_config_dir, custom_model_dict):
    """Test 'gpu-session models remove' respects cancellation."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={"my-custom-model": custom_model_dict},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    # Mock confirmation as "no"
    mocker.patch("questionary.confirm", return_value=mocker.Mock(ask=lambda: False))

    result = runner.invoke(app, ["models", "remove", "my-custom-model"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "cancelled" in result.stdout.lower() or "not removed" in result.stdout.lower()

    # Verify save was NOT called
    mock_manager.save.assert_not_called()


def test_models_remove_builtin_model_fails(mocker, temp_config_dir):
    """Test 'gpu-session models remove' rejects built-in models."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    # Try to remove a known built-in model
    result = runner.invoke(app, ["models", "remove", "deepseek-r1-70b"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "error" in result.stdout.lower()
    assert "cannot remove built-in model" in result.stdout.lower()
    assert "deepseek-r1-70b" in result.stdout.lower()

    # Verify save was NOT called
    mock_manager.save.assert_not_called()


def test_models_remove_nonexistent_custom_model_fails(mocker, temp_config_dir):
    """Test 'gpu-session models remove' fails for non-existent custom model."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    result = runner.invoke(app, ["models", "remove", "nonexistent-model"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "error" in result.stdout.lower()
    assert "custom model" in result.stdout.lower()
    assert "not found" in result.stdout.lower()
    assert "nonexistent-model" in result.stdout.lower()

    # Verify save was NOT called
    mock_manager.save.assert_not_called()


def test_models_remove_with_no_config_fails(mocker, temp_config_dir):
    """Test 'gpu-session models remove' fails when not configured."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = None

    result = runner.invoke(app, ["models", "remove", "some-model"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "not configured" in result.stdout.lower()

    # Verify save was NOT called
    mock_manager.save.assert_not_called()
