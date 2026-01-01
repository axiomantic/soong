"""Tests for config.py configuration management."""

import pytest
from gpu_session.config import validate_custom_model


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
