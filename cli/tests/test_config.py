"""Tests for config.py configuration management."""

import pytest
from gpu_session.config import validate_custom_model, Config, LambdaConfig, StatusDaemonConfig


def test_validate_custom_model_valid():
    """Test validate_custom_model accepts valid model."""
    valid_data = {
        "hf_path": "custom-org/custom-model",
        "params_billions": 13.0,
        "quantization": "int4",
        "context_length": 8192,
        "good_for": ["Code generation", "Testing"],
        "not_good_for": ["Production use"],
        "notes": "Test custom model",
    }
    # Should not raise
    validate_custom_model(valid_data)


def test_validate_custom_model_missing_required_field():
    """Test validate_custom_model rejects missing required fields."""
    invalid_data = {
        "hf_path": "org/model",
        # Missing params_billions, quantization, context_length
    }

    with pytest.raises(ValueError, match="Missing required fields"):
        validate_custom_model(invalid_data)


def test_validate_custom_model_invalid_quantization():
    """Test validate_custom_model rejects invalid quantization."""
    invalid_data = {
        "hf_path": "org/model",
        "params_billions": 7.0,
        "quantization": "invalid_quant",
        "context_length": 4096,
    }

    with pytest.raises(ValueError, match="Invalid quantization"):
        validate_custom_model(invalid_data)


def test_validate_custom_model_negative_params():
    """Test validate_custom_model rejects negative params."""
    invalid_data = {
        "hf_path": "org/model",
        "params_billions": -7.0,
        "quantization": "int4",
        "context_length": 4096,
    }

    with pytest.raises(ValueError, match="must be a positive number"):
        validate_custom_model(invalid_data)


def test_validate_custom_model_invalid_context():
    """Test validate_custom_model rejects context < 512."""
    invalid_data = {
        "hf_path": "org/model",
        "params_billions": 7.0,
        "quantization": "int4",
        "context_length": 256,  # Too small
    }

    with pytest.raises(ValueError, match="context_length must be"):
        validate_custom_model(invalid_data)


# Task A1 Tests: Config Dataclass custom_models field


def test_config_has_custom_models_field():
    """Test Config dataclass has custom_models field."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
    )
    assert hasattr(config, "custom_models")
    assert isinstance(config.custom_models, dict)


def test_config_custom_models_defaults_to_empty_dict():
    """Test custom_models defaults to empty dict in __post_init__."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
    )
    assert config.custom_models == {}


def test_config_custom_models_can_be_provided():
    """Test custom_models can be explicitly provided."""
    custom = {
        "my-model": {
            "hf_path": "org/model",
            "params_billions": 7.0,
            "quantization": "int4",
            "context_length": 4096,
        }
    }
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        custom_models=custom,
    )
    assert config.custom_models == custom
