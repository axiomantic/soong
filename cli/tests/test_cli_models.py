"""Tests for 'gpu-session models' CLI commands."""

import pytest
from typer.testing import CliRunner
from gpu_session.cli import app
from gpu_session.models import KNOWN_MODELS


runner = CliRunner()


def test_models_list_displays_all_known_models(mocker, temp_config_dir, sample_config):
    """Test 'gpu-session models' lists all known models."""
    # Mock config manager
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    result = runner.invoke(app, ["models"], catch_exceptions=False)

    assert result.exit_code == 0

    # Should show table header
    assert "Available Models" in result.stdout
    assert "ID" in result.stdout
    assert "Params" in result.stdout
    assert "Quant" in result.stdout
    assert "VRAM" in result.stdout
    assert "Min GPU" in result.stdout

    # Should show at least one known model
    assert "deepseek-r1-70b" in result.stdout or "qwen2.5-coder" in result.stdout


def test_models_list_shows_custom_model_count(mocker, temp_config_dir, custom_model_dict):
    """Test 'gpu-session models' shows custom model count."""
    from gpu_session.config import Config, LambdaConfig, StatusDaemonConfig

    config = Config(
        lambda_config=LambdaConfig(api_key="test"),
        status_daemon=StatusDaemonConfig(token="test"),
        custom_models={"my-custom-1": custom_model_dict},
    )

    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = config

    result = runner.invoke(app, ["models"])

    assert result.exit_code == 0
    assert "Custom models: 1 configured" in result.stdout
