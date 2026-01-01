"""Tests for models.py VRAM calculation and model registry."""

import pytest
from gpu_session.models import ModelConfig, Quantization


def test_model_config_from_dict_valid(custom_model_dict):
    """Test ModelConfig.from_dict() with valid data."""
    config = ModelConfig.from_dict("custom-13b", custom_model_dict)

    assert config.model_id == "custom-13b"
    assert config.hf_path == "custom-org/custom-model"
    assert config.params_billions == 13.0
    assert config.default_quantization == Quantization.INT4
    assert config.context_length == 8192


def test_model_config_from_dict_invalid_quantization():
    """Test ModelConfig.from_dict() rejects invalid quantization."""
    data = {
        "hf_path": "org/model",
        "params_billions": 7.0,
        "quantization": "invalid",
        "context_length": 4096,
    }

    with pytest.raises(ValueError, match="Invalid quantization"):
        ModelConfig.from_dict("test", data)


def test_model_config_from_dict_missing_field():
    """Test ModelConfig.from_dict() rejects missing required fields."""
    data = {
        "hf_path": "org/model",
        # Missing params_billions
        "quantization": "int4",
    }

    with pytest.raises(KeyError):
        ModelConfig.from_dict("test", data)
