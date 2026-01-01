"""Shared pytest fixtures for gpu-session tests.

Test Naming Conventions:
- test_<function_name>_<scenario>() for unit tests
  Example: test_estimate_vram_llama_70b_int4()

- test_<command>_<behavior>() for CLI command tests
  Example: test_models_list_displays_all_known_models()

- test_<class_name>_<method>_<scenario>() for class method tests
  Example: test_model_config_from_dict_valid()

- test_<integration_workflow>() for end-to-end tests
  Example: test_full_workflow_configure_add_model_start()

Use descriptive scenario suffixes:
- _valid, _invalid for validation tests
- _missing_field, _negative_params for error cases
- _happy_path, _edge_case for behavior tests
"""

import pytest
from pathlib import Path
from gpu_session.models import ModelConfig, Quantization
from gpu_session.config import Config, LambdaConfig, StatusDaemonConfig, DefaultsConfig, SSHConfig


@pytest.fixture
def sample_model_config():
    """Standard 70B INT4 model for testing."""
    return ModelConfig(
        name="Test Model 70B",
        model_id="test-model-70b",
        hf_path="test-org/test-model-70b",
        params_billions=70.0,
        default_quantization=Quantization.INT4,
        context_length=4096,
        description="Test model for unit tests",
    )


@pytest.fixture
def small_model_config():
    """Small 7B FP16 model for testing."""
    return ModelConfig(
        name="Test Model 7B",
        model_id="test-model-7b",
        hf_path="test-org/test-model-7b",
        params_billions=7.0,
        default_quantization=Quantization.FP16,
        context_length=4096,
        description="Small test model",
    )


@pytest.fixture
def custom_model_dict():
    """Valid custom model dictionary for testing."""
    return {
        "hf_path": "custom-org/custom-model",
        "params_billions": 13.0,
        "quantization": "int4",
        "context_length": 8192,
        "good_for": ["Code generation", "Testing"],
        "not_good_for": ["Production use"],
        "notes": "Test custom model",
    }


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary config directory for integration tests."""
    config_dir = tmp_path / ".config" / "gpu-session"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def sample_config(temp_config_dir):
    """Sample Config object for testing."""
    return Config(
        lambda_config=LambdaConfig(
            api_key="test_key_12345",
            default_region="us-west-1",
            filesystem_name="test-fs",
        ),
        status_daemon=StatusDaemonConfig(
            token="test_token_67890",
            port=8080,
        ),
        defaults=DefaultsConfig(
            model="deepseek-r1-70b",
            gpu="gpu_1x_a100_sxm4_80gb",
            lease_hours=4,
        ),
        ssh=SSHConfig(
            key_path="~/.ssh/id_rsa",
        ),
    )


@pytest.fixture
def mock_lambda_api(mocker):
    """Mock Lambda API responses."""
    mock_api = mocker.Mock()

    # Mock instance types
    mock_api.list_instance_types.return_value = [
        mocker.Mock(
            name="gpu_1x_a10",
            description="1x A10 (24 GB)",
            price_cents_per_hour=60,
            regions_available=["us-west-1"],
            price_per_hour=0.60,
        ),
        mocker.Mock(
            name="gpu_1x_a6000",
            description="1x A6000 (48 GB)",
            price_cents_per_hour=80,
            regions_available=["us-west-1", "us-east-1"],
            price_per_hour=0.80,
        ),
        mocker.Mock(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=129,
            regions_available=["us-west-1"],
            price_per_hour=1.29,
        ),
    ]

    return mock_api
