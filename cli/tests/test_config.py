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


# Task: Config Load/Save Serialization for custom_models


def test_config_save_includes_custom_models(tmp_path):
    """Test Config.save() writes custom_models to YAML."""
    from gpu_session.config import ConfigManager

    # Create config with custom models
    custom_models = {
        "test-model": {
            "hf_path": "test-org/test-model",
            "params_billions": 13.0,
            "quantization": "int4",
            "context_length": 8192,
        }
    }
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        custom_models=custom_models,
    )

    # Save to temp directory
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(config)

    # Read YAML and verify custom_models is present
    import yaml
    with open(manager.config_file) as f:
        data = yaml.safe_load(f)

    assert "custom_models" in data
    assert data["custom_models"] == custom_models


def test_config_load_reads_custom_models(tmp_path):
    """Test Config.load() reads custom_models from YAML."""
    from gpu_session.config import ConfigManager
    import yaml

    # Create YAML with custom_models
    custom_models = {
        "loaded-model": {
            "hf_path": "loaded-org/model",
            "params_billions": 7.0,
            "quantization": "fp16",
            "context_length": 4096,
        }
    }
    yaml_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
        "custom_models": custom_models,
    }

    # Write YAML file
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(yaml_data, f)

    # Load and verify
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = config_file
    config = manager.load()

    assert config.custom_models == custom_models


def test_config_load_defaults_to_empty_dict_when_missing(tmp_path):
    """Test Config.load() defaults custom_models to empty dict if missing from YAML."""
    from gpu_session.config import ConfigManager
    import yaml

    # Create YAML without custom_models
    yaml_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
    }

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(yaml_data, f)

    # Load and verify
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = config_file
    config = manager.load()

    assert config.custom_models == {}


def test_config_roundtrip_preserves_custom_models(tmp_path):
    """Test save then load preserves custom_models exactly."""
    from gpu_session.config import ConfigManager

    # Create config with custom models
    custom_models = {
        "model-1": {
            "hf_path": "org1/model1",
            "params_billions": 7.0,
            "quantization": "int4",
            "context_length": 4096,
        },
        "model-2": {
            "hf_path": "org2/model2",
            "params_billions": 13.0,
            "quantization": "fp16",
            "context_length": 8192,
        },
    }
    original_config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        custom_models=custom_models,
    )

    # Save
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(original_config)

    # Load
    loaded_config = manager.load()

    # Verify custom_models preserved exactly
    assert loaded_config.custom_models == original_config.custom_models


def test_config_load_validates_custom_models(tmp_path):
    """Test Config.load() validates custom models and logs warnings for invalid ones."""
    from gpu_session.config import ConfigManager
    import yaml
    import logging

    # Create YAML with mix of valid and invalid custom models
    yaml_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
        "custom_models": {
            "valid-model": {
                "hf_path": "org/valid",
                "params_billions": 7.0,
                "quantization": "int4",
                "context_length": 4096,
            },
            "invalid-model": {
                "hf_path": "org/invalid",
                # Missing params_billions, quantization, context_length
            },
        },
    }

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(yaml_data, f)

    # Load with logging capture
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = config_file

    with pytest.warns(None) as warning_list:
        config = manager.load()

    # Should still load successfully (not fail)
    assert config is not None
    # Both models should be preserved (validation warnings only)
    assert "valid-model" in config.custom_models
    assert "invalid-model" in config.custom_models
