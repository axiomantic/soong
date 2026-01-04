"""Tests for pre-launch validation module."""

import pytest
from unittest.mock import Mock, patch

from soong.validation import (
    ValidationError,
    ValidationWarning,
    ValidationResult,
    LaunchValidator,
)
from soong.lambda_api import LambdaAPI, InstanceType, FileSystem, LambdaAPIError


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_fields(self):
        error = ValidationError(
            message="GPU not found",
            suggestion="Try a different GPU"
        )
        assert error.message == "GPU not found"
        assert error.suggestion == "Try a different GPU"


class TestValidationWarning:
    """Tests for ValidationWarning dataclass."""

    def test_validation_warning_fields(self):
        warning = ValidationWarning(
            message="No capacity",
            suggestion="Try another region"
        )
        assert warning.message == "No capacity"
        assert warning.suggestion == "Try another region"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_can_launch_no_errors(self):
        result = ValidationResult(errors=[], warnings=[])
        assert result.can_launch is True

    def test_can_launch_with_errors(self):
        result = ValidationResult(
            errors=[ValidationError(message="Error", suggestion="Fix it")],
            warnings=[]
        )
        assert result.can_launch is False

    def test_can_launch_warnings_only(self):
        result = ValidationResult(
            errors=[],
            warnings=[ValidationWarning(message="Warning", suggestion="Note")]
        )
        assert result.can_launch is True

    def test_can_launch_errors_and_warnings(self):
        result = ValidationResult(
            errors=[ValidationError(message="Error", suggestion="Fix")],
            warnings=[ValidationWarning(message="Warning", suggestion="Note")]
        )
        assert result.can_launch is False


class TestLaunchValidatorGPU:
    """Tests for GPU validation in LaunchValidator."""

    @pytest.fixture
    def mock_api(self):
        api = Mock(spec=LambdaAPI)
        api.list_instance_types.return_value = [
            InstanceType(
                name="gpu_1x_a100",
                description="1x A100",
                price_cents_per_hour=100,
                vcpus=8,
                memory_gib=64,
                storage_gib=500,
                regions_available=["us-west-1", "us-east-1"],
            ),
            InstanceType(
                name="gpu_1x_gh200",
                description="1x GH200",
                price_cents_per_hour=150,
                vcpus=8,
                memory_gib=96,
                storage_gib=500,
                regions_available=["us-east-3"],
            ),
        ]
        api.list_file_systems.return_value = []
        api.list_ssh_keys.return_value = ["my-key"]
        return api

    def test_validate_gpu_type_exists(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is True
        assert len(result.errors) == 0

    def test_validate_gpu_type_not_found(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_h200",  # Doesn't exist
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message
        assert "Available:" in result.errors[0].suggestion

    def test_validate_gpu_no_capacity_in_region(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_gh200",  # Only in us-east-3
            region="us-west-1",  # Not available here
            filesystem_name=None,
            ssh_key_names=["my-key"],
        )
        # Should be warning, not error
        assert result.can_launch is True
        assert len(result.warnings) == 1
        assert "No capacity" in result.warnings[0].message
        assert "us-east-3" in result.warnings[0].suggestion

    def test_validate_gpu_no_capacity_anywhere(self, mock_api):
        mock_api.list_instance_types.return_value = [
            InstanceType(
                name="gpu_1x_a100",
                description="1x A100",
                price_cents_per_hour=100,
                vcpus=8,
                memory_gib=64,
                storage_gib=500,
                regions_available=[],  # No capacity anywhere
            ),
        ]
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is True
        assert len(result.warnings) == 1
        assert "No current capacity" in result.warnings[0].message
        assert "any region" in result.warnings[0].message

    def test_validate_gpu_api_failure(self, mock_api):
        mock_api.list_instance_types.side_effect = LambdaAPIError("API down")
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["my-key"],
        )
        # Should be warning, not error (graceful degradation)
        assert result.can_launch is True
        assert len(result.warnings) == 1
        assert "API error" in result.warnings[0].message


class TestLaunchValidatorFilesystem:
    """Tests for filesystem validation in LaunchValidator."""

    @pytest.fixture
    def mock_api(self):
        api = Mock(spec=LambdaAPI)
        api.list_instance_types.return_value = [
            InstanceType(
                name="gpu_1x_a100",
                description="1x A100",
                price_cents_per_hour=100,
                vcpus=8,
                memory_gib=64,
                storage_gib=500,
                regions_available=["us-west-1", "us-east-3"],
            ),
        ]
        api.list_file_systems.return_value = [
            FileSystem(
                id="fs-123",
                name="data",
                region="us-east-3",
                mount_point="/lambda/nfs/data",
                is_in_use=False,
            ),
        ]
        api.list_ssh_keys.return_value = ["my-key"]
        return api

    def test_validate_filesystem_exists(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-east-3",
            filesystem_name="data",
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is True
        assert len(result.errors) == 0

    def test_validate_filesystem_not_found(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-east-3",
            filesystem_name="coding-stack",  # Doesn't exist
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message
        assert "data" in result.errors[0].suggestion  # Available filesystem

    def test_validate_filesystem_wrong_region(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",  # Filesystem is in us-east-3
            filesystem_name="data",
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "us-east-3" in result.errors[0].message
        assert "us-west-1" in result.errors[0].message
        assert "--region us-east-3" in result.errors[0].suggestion

    def test_validate_filesystem_none(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,  # No filesystem
            ssh_key_names=["my-key"],
        )
        # Should skip filesystem validation
        assert result.can_launch is True

    def test_validate_filesystem_empty_string(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name="",  # Empty string
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "cannot be empty" in result.errors[0].message

    def test_validate_filesystem_whitespace(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name="   ",  # Whitespace only
            ssh_key_names=["my-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "cannot be empty" in result.errors[0].message

    def test_validate_filesystem_api_failure(self, mock_api):
        mock_api.list_file_systems.side_effect = LambdaAPIError("API down")
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name="data",
            ssh_key_names=["my-key"],
        )
        # Should be warning, not error (graceful degradation)
        assert result.can_launch is True
        assert any("API error" in w.message for w in result.warnings)


class TestLaunchValidatorSSHKeys:
    """Tests for SSH key validation in LaunchValidator."""

    @pytest.fixture
    def mock_api(self):
        api = Mock(spec=LambdaAPI)
        api.list_instance_types.return_value = [
            InstanceType(
                name="gpu_1x_a100",
                description="1x A100",
                price_cents_per_hour=100,
                vcpus=8,
                memory_gib=64,
                storage_gib=500,
                regions_available=["us-west-1"],
            ),
        ]
        api.list_file_systems.return_value = []
        api.list_ssh_keys.return_value = ["key1", "key2"]
        return api

    def test_validate_ssh_keys_all_exist(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["key1"],
        )
        assert result.can_launch is True
        assert len(result.errors) == 0

    def test_validate_ssh_key_not_found(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["missing-key"],
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message
        assert "cloud.lambda.ai" in result.errors[0].suggestion

    def test_validate_ssh_keys_empty_list(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=[],  # Empty
        )
        assert result.can_launch is False
        assert len(result.errors) == 1
        assert "No SSH keys provided" in result.errors[0].message

    def test_validate_ssh_keys_duplicates(self, mock_api):
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["key1", "key1", "key2"],  # Duplicates
        )
        # Should deduplicate and not report same key twice
        assert result.can_launch is True
        # API should only be called once per unique key
        assert len(result.errors) == 0

    def test_validate_ssh_keys_api_failure(self, mock_api):
        mock_api.list_ssh_keys.side_effect = LambdaAPIError("API down")
        validator = LaunchValidator(mock_api)
        result = validator.validate(
            gpu_type="gpu_1x_a100",
            region="us-west-1",
            filesystem_name=None,
            ssh_key_names=["key1"],
        )
        # Should be warning, not error (graceful degradation)
        assert result.can_launch is True
        assert any("API error" in w.message for w in result.warnings)


class TestLaunchValidatorCaching:
    """Tests for API response caching in LaunchValidator."""

    @pytest.fixture
    def mock_api(self):
        api = Mock(spec=LambdaAPI)
        api.list_instance_types.return_value = [
            InstanceType(
                name="gpu_1x_a100",
                description="1x A100",
                price_cents_per_hour=100,
                vcpus=8,
                memory_gib=64,
                storage_gib=500,
                regions_available=["us-west-1"],
            ),
        ]
        api.list_file_systems.return_value = []
        api.list_ssh_keys.return_value = ["my-key"]
        return api

    def test_validator_caches_instance_types(self, mock_api):
        validator = LaunchValidator(mock_api)
        # Call validate twice
        validator.validate("gpu_1x_a100", "us-west-1", None, ["my-key"])
        validator.validate("gpu_1x_a100", "us-west-1", None, ["my-key"])
        # API should only be called once (cached)
        assert mock_api.list_instance_types.call_count == 1

    def test_validator_caches_file_systems(self, mock_api):
        validator = LaunchValidator(mock_api)
        # First call without filesystem
        validator.validate("gpu_1x_a100", "us-west-1", None, ["my-key"])
        # Second call with filesystem (should trigger file systems API)
        validator.validate("gpu_1x_a100", "us-west-1", "data", ["my-key"])
        # Third call with filesystem (should use cache)
        validator.validate("gpu_1x_a100", "us-west-1", "data", ["my-key"])
        # File systems API should only be called once
        assert mock_api.list_file_systems.call_count == 1


class TestLaunchValidatorFormatting:
    """Tests for error message formatting in LaunchValidator."""

    @pytest.fixture
    def mock_api(self):
        api = Mock(spec=LambdaAPI)
        api.list_file_systems.return_value = []
        api.list_ssh_keys.return_value = ["my-key"]
        return api

    def test_format_available_gpus_zero(self, mock_api):
        mock_api.list_instance_types.return_value = []
        validator = LaunchValidator(mock_api)
        result = validator._format_available_gpus([])
        assert result == "none available"

    def test_format_available_gpus_few(self, mock_api):
        mock_api.list_instance_types.return_value = []
        types = [
            InstanceType("gpu_1", "GPU 1", 100, 8, 64, 500, []),
            InstanceType("gpu_2", "GPU 2", 100, 8, 64, 500, []),
        ]
        validator = LaunchValidator(mock_api)
        result = validator._format_available_gpus(types)
        assert result == "gpu_1, gpu_2"
        assert "..." not in result

    def test_format_available_gpus_many(self, mock_api):
        mock_api.list_instance_types.return_value = []
        types = [
            InstanceType(f"gpu_{i}", f"GPU {i}", 100, 8, 64, 500, [])
            for i in range(10)
        ]
        validator = LaunchValidator(mock_api)
        result = validator._format_available_gpus(types)
        assert "..." in result
        assert "(5 more)" in result
