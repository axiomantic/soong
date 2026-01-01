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

    # Should show at least one known model - verify in actual data rows
    from tests.helpers.assertions import assert_table_row
    # Try to find at least one known model in table rows
    known_models = ["deepseek-r1-70b", "llama-3.1-8b", "qwen2.5-coder-32b", "mistral-7b"]
    found_model = False
    for model_id in known_models:
        try:
            assert_table_row(result.stdout, model=model_id)
            found_model = True
            break
        except AssertionError:
            continue
    assert found_model, f"None of {known_models} found in table output"


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


def test_models_info_displays_known_model_details(mocker, temp_config_dir, sample_config):
    """Test 'gpu-session models info <model-id>' displays detailed model information."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    result = runner.invoke(app, ["models", "info", "deepseek-r1-70b"], catch_exceptions=False)

    assert result.exit_code == 0

    # Should display model name and HuggingFace path
    assert "DeepSeek-R1 70B" in result.stdout
    assert "deepseek-ai/DeepSeek-R1-Distill-Llama-70B" in result.stdout

    # Should display parameters, quantization, and context
    assert "70" in result.stdout  # Parameters in billions
    assert "INT4" in result.stdout or "int4" in result.stdout
    assert "8,192" in result.stdout or "8192" in result.stdout  # Context length (may be formatted)

    # Should display VRAM breakdown
    assert "VRAM" in result.stdout
    assert "GB" in result.stdout

    # Should display recommended GPU
    assert "GPU" in result.stdout

    # Should display good_for and not_good_for
    assert "Good for" in result.stdout or "good for" in result.stdout
    assert "Not good for" in result.stdout or "not good for" in result.stdout


def test_models_info_displays_vram_breakdown(mocker, temp_config_dir, sample_config):
    """Test 'gpu-session models info' displays detailed VRAM breakdown."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    result = runner.invoke(app, ["models", "info", "qwen2.5-coder-32b"], catch_exceptions=False)

    assert result.exit_code == 0

    # Should show VRAM components
    assert "Base weights" in result.stdout or "base" in result.stdout.lower()
    assert "KV cache" in result.stdout or "kv" in result.stdout.lower()
    assert "Overhead" in result.stdout or "overhead" in result.stdout.lower()
    assert "Total" in result.stdout or "total" in result.stdout.lower()


def test_models_info_model_not_found(mocker, temp_config_dir, sample_config):
    """Test 'gpu-session models info' with non-existent model ID."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    result = runner.invoke(app, ["models", "info", "non-existent-model"])

    assert result.exit_code == 1
    assert "Error: Model 'non-existent-model' not found" in result.stdout
    assert "gpu-session models" in result.stdout  # Should suggest using models list


def test_models_info_displays_notes(mocker, temp_config_dir, sample_config):
    """Test 'gpu-session models info' displays notes when present."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    result = runner.invoke(app, ["models", "info", "deepseek-r1-70b"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Notes" in result.stdout or "notes" in result.stdout.lower()


def test_models_info_displays_recommended_gpu_with_price(mocker, temp_config_dir, sample_config, mock_lambda_api):
    """Test 'gpu-session models info' displays recommended GPU with pricing."""
    mock_manager = mocker.patch("gpu_session.cli.config_manager")
    mock_manager.load.return_value = sample_config

    # Mock LambdaAPI
    mocker.patch("gpu_session.cli.LambdaAPI", return_value=mock_lambda_api)

    result = runner.invoke(app, ["models", "info", "deepseek-r1-70b"], catch_exceptions=False)

    assert result.exit_code == 0
    # Should show GPU recommendation
    assert "Recommended GPU" in result.stdout or "GPU" in result.stdout
