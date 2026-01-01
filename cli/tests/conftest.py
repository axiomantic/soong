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


# HTTP Mocking Fixtures (Pattern #5 fix: Use responses library instead of mocking requests)
import responses


@pytest.fixture
def mock_http():
    """HTTP mocking context using responses library.

    Use this instead of mocker.patch("requests.post/get/etc") to ensure
    the actual HTTP logic is tested, not just that a mock was called.

    Example:
        def test_api_call(mock_http):
            mock_http.add(
                responses.POST,
                "https://api.example.com/endpoint",
                json={"status": "success"},
                status=200,
            )
            # Call code that makes HTTP request
            result = my_function()
            # Verify the request was made correctly
            assert len(mock_http.calls) == 1
            assert mock_http.calls[0].request.headers["Authorization"] == "Bearer token"
    """
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def lambda_api_base_url():
    """Base URL for Lambda Labs API."""
    return "https://cloud.lambdalabs.com/api/v1"


@pytest.fixture
def mock_lambda_http(mock_http, lambda_api_base_url):
    """Pre-configured HTTP mocks for Lambda Labs API endpoints.

    Returns the responses mock with common endpoints configured.
    """
    # Common instance data used across tests
    mock_http._test_instance = {
        "id": "inst_abc123xyz",
        "name": "test-instance",
        "ip": "1.2.3.4",
        "status": "active",
        "instance_type": {
            "name": "gpu_1x_a100_sxm4_80gb",
            "description": "1x A100 SXM4 (80 GB)",
            "price_cents_per_hour": 129,
        },
        "region": {
            "name": "us-west-1",
            "description": "US West 1",
        },
        "ssh_key_names": ["my-key"],
        "hostname": "test-instance.cloud.lambdalabs.com",
    }

    # Default instance list endpoint
    mock_http.add(
        responses.GET,
        f"{lambda_api_base_url}/instances",
        json={"data": [mock_http._test_instance]},
        status=200,
    )

    return mock_http


@pytest.fixture
def mock_instance(mocker):
    """Create a mock instance object with realistic data.

    Use unique values that would fail if hardcoded to catch Pattern #4 issues.
    """
    instance = mocker.Mock()
    instance.id = "inst_unique_789xyz"  # Unique ID to catch hardcoding
    instance.name = "unique-test-instance"
    instance.ip = "192.168.99.42"  # Unique IP
    instance.status = "active"
    instance.instance_type = mocker.Mock(
        name="gpu_1x_a100_sxm4_80gb",
        description="1x A100 SXM4 (80 GB)",
        price_cents_per_hour=129,
        price_per_hour=1.29,
    )
    instance.region = mocker.Mock(
        name="us-west-1",
        description="US West 1",
    )
    instance.ssh_key_names = ["my-key"]
    instance.hostname = "unique-test.cloud.lambdalabs.com"
    instance.launched_at = "2025-01-01T12:00:00Z"

    return instance


@pytest.fixture
def cli_runner():
    """Typer CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()
