"""Tests for lambda_api.py Lambda Labs API client."""

import pytest
import requests
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from gpu_session.lambda_api import (
    InstanceType,
    Instance,
    LambdaAPI,
    LambdaAPIError,
)


class TestInstanceType:
    """Test InstanceType dataclass and methods."""

    def test_from_api_response_valid(self):
        """Test creating InstanceType from valid API response."""
        api_data = {
            "instance_type": {
                "description": "1x A100 SXM4 (80 GB)",
                "price_cents_per_hour": 129,
                "specs": {
                    "vcpus": 30,
                    "memory_gib": 200,
                    "storage_gib": 512,
                }
            },
            "regions_with_capacity_available": [
                {"name": "us-west-1"},
                {"name": "us-east-1"},
            ]
        }

        instance_type = InstanceType.from_api_response("gpu_1x_a100_sxm4_80gb", api_data)

        assert instance_type.name == "gpu_1x_a100_sxm4_80gb"
        assert instance_type.description == "1x A100 SXM4 (80 GB)"
        assert instance_type.price_cents_per_hour == 129
        assert instance_type.vcpus == 30
        assert instance_type.memory_gib == 200
        assert instance_type.storage_gib == 512
        assert instance_type.regions_available == ["us-west-1", "us-east-1"]

    def test_from_api_response_missing_fields(self):
        """Test creating InstanceType with missing optional fields."""
        api_data = {
            "instance_type": {},
            "regions_with_capacity_available": []
        }

        instance_type = InstanceType.from_api_response("test-gpu", api_data)

        assert instance_type.name == "test-gpu"
        assert instance_type.description == "test-gpu"  # Defaults to name
        assert instance_type.price_cents_per_hour == 0
        assert instance_type.vcpus == 0
        assert instance_type.memory_gib == 0
        assert instance_type.storage_gib == 0
        assert instance_type.regions_available == []

    def test_from_api_response_empty_specs(self):
        """Test creating InstanceType with empty specs dict."""
        api_data = {
            "instance_type": {
                "description": "Test GPU",
                "price_cents_per_hour": 100,
                "specs": {}
            },
            "regions_with_capacity_available": []
        }

        instance_type = InstanceType.from_api_response("test-gpu", api_data)

        assert instance_type.vcpus == 0
        assert instance_type.memory_gib == 0
        assert instance_type.storage_gib == 0

    def test_price_per_hour_conversion(self):
        """Test price_per_hour property converts cents to dollars."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=["us-west-1"]
        )

        assert instance_type.price_per_hour == 1.29

    def test_price_per_hour_zero(self):
        """Test price_per_hour with zero cents."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=0,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        assert instance_type.price_per_hour == 0.0

    def test_format_price(self):
        """Test format_price returns formatted string."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=["us-west-1"]
        )

        assert instance_type.format_price() == "$1.29/hr"

    def test_format_price_rounds_correctly(self):
        """Test format_price rounds to 2 decimal places."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=12345,  # $123.45
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        assert instance_type.format_price() == "$123.45/hr"

    def test_estimate_cost_single_hour(self):
        """Test estimate_cost for 1 hour."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        assert instance_type.estimate_cost(1) == 1.29

    def test_estimate_cost_multiple_hours(self):
        """Test estimate_cost for multiple hours."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        # 10 hours at $1.29/hr = $12.90
        assert instance_type.estimate_cost(10) == 12.90

    def test_estimate_cost_zero_hours(self):
        """Test estimate_cost with zero hours."""
        instance_type = InstanceType(
            name="test-gpu",
            description="Test",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        assert instance_type.estimate_cost(0) == 0.0

    def test_format_for_selection_with_availability(self):
        """Test format_for_selection with available capacity."""
        instance_type = InstanceType(
            name="test-gpu",
            description="1x A100 (80 GB)",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=["us-west-1"]
        )

        result = instance_type.format_for_selection()
        assert result == "1x A100 (80 GB) - $1.29/hr (available)"

    def test_format_for_selection_no_availability(self):
        """Test format_for_selection with no available capacity."""
        instance_type = InstanceType(
            name="test-gpu",
            description="1x A100 (80 GB)",
            price_cents_per_hour=129,
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=[]
        )

        result = instance_type.format_for_selection()
        assert result == "1x A100 (80 GB) - $1.29/hr (no capacity)"


class TestInstance:
    """Test Instance dataclass and methods."""

    def test_from_api_response_valid(self):
        """Test creating Instance from valid API response."""
        api_data = {
            "id": "instance-123",
            "name": "my-instance",
            "ip": "192.168.1.100",
            "status": "active",
            "instance_type": {"name": "gpu_1x_a100_sxm4_80gb"},
            "region": {"name": "us-west-1"},
            "created_at": "2025-01-01T10:00:00Z",
            "lease_expires_at": "2025-01-01T14:00:00Z",
        }

        instance = Instance.from_api_response(api_data)

        assert instance.id == "instance-123"
        assert instance.name == "my-instance"
        assert instance.ip == "192.168.1.100"
        assert instance.status == "active"
        assert instance.instance_type == "gpu_1x_a100_sxm4_80gb"
        assert instance.region == "us-west-1"
        assert instance.created_at == "2025-01-01T10:00:00Z"
        assert instance.lease_expires_at == "2025-01-01T14:00:00Z"

    def test_from_api_response_missing_optional_fields(self):
        """Test creating Instance with missing optional fields."""
        api_data = {
            "id": "instance-123",
            "status": "booting",
            "instance_type": {"name": "gpu_1x_a10"},
            "region": {"name": "us-east-1"},
            "created_at": "2025-01-01T10:00:00Z",
        }

        instance = Instance.from_api_response(api_data)

        assert instance.id == "instance-123"
        assert instance.name is None
        assert instance.ip is None
        assert instance.status == "booting"
        assert instance.lease_expires_at is None

    def test_is_lease_expired_no_expiration(self):
        """Test is_lease_expired returns False when no expiration set."""
        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=None,
        )

        assert instance.is_lease_expired() is False

    def test_is_lease_expired_future_expiration(self):
        """Test is_lease_expired returns False for future expiration."""
        future_time = datetime.utcnow() + timedelta(hours=2)
        future_iso = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=future_iso,
        )

        assert instance.is_lease_expired() is False

    def test_is_lease_expired_past_expiration(self):
        """Test is_lease_expired returns True for past expiration."""
        past_time = datetime.utcnow() - timedelta(hours=2)
        past_iso = past_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=past_iso,
        )

        assert instance.is_lease_expired() is True

    def test_is_lease_expired_invalid_timestamp(self):
        """Test is_lease_expired handles invalid timestamp gracefully."""
        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at="invalid-timestamp",
        )

        assert instance.is_lease_expired() is False

    def test_is_lease_expired_with_timezone(self):
        """Test is_lease_expired handles timezone-aware timestamps."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        past_iso = past_time.isoformat()

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=past_iso,
        )

        assert instance.is_lease_expired() is True

    def test_lease_status_style_no_expiration(self):
        """Test lease_status_style returns white when no expiration."""
        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=None,
        )

        assert instance.lease_status_style() == "white"

    def test_lease_status_style_expired(self):
        """Test lease_status_style returns red when expired."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        past_iso = past_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=past_iso,
        )

        assert instance.lease_status_style() == "red"

    def test_lease_status_style_expiring_soon(self):
        """Test lease_status_style returns yellow when expiring soon (< 1 hour)."""
        future_time = datetime.utcnow() + timedelta(minutes=30)
        future_iso = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=future_iso,
        )

        assert instance.lease_status_style() == "yellow"

    def test_lease_status_style_safe(self):
        """Test lease_status_style returns green when expiration is far."""
        future_time = datetime.utcnow() + timedelta(hours=3)
        future_iso = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at=future_iso,
        )

        assert instance.lease_status_style() == "green"

    def test_lease_status_style_invalid_timestamp(self):
        """Test lease_status_style handles invalid timestamp gracefully."""
        instance = Instance(
            id="instance-123",
            name="test",
            ip="192.168.1.100",
            status="active",
            instance_type="gpu_1x_a100_sxm4_80gb",
            region="us-west-1",
            created_at="2025-01-01T10:00:00Z",
            lease_expires_at="invalid-timestamp",
        )

        assert instance.lease_status_style() == "white"


class TestLambdaAPIError:
    """Test LambdaAPIError exception."""

    def test_exception_can_be_raised(self):
        """Test LambdaAPIError can be raised and caught."""
        with pytest.raises(LambdaAPIError):
            raise LambdaAPIError("Test error")

    def test_exception_message(self):
        """Test LambdaAPIError preserves message."""
        with pytest.raises(LambdaAPIError, match="Test error message"):
            raise LambdaAPIError("Test error message")

    def test_exception_is_exception_subclass(self):
        """Test LambdaAPIError is subclass of Exception."""
        assert issubclass(LambdaAPIError, Exception)


class TestLambdaAPIInit:
    """Test LambdaAPI initialization."""

    def test_init_sets_api_key(self):
        """Test __init__ sets API key."""
        api = LambdaAPI("test-api-key-12345")
        assert api.api_key == "test-api-key-12345"

    def test_init_creates_session(self):
        """Test __init__ creates requests session."""
        api = LambdaAPI("test-key")
        assert isinstance(api.session, requests.Session)

    def test_init_sets_authorization_header(self):
        """Test __init__ sets Authorization header."""
        api = LambdaAPI("test-key-secret")
        assert api.session.headers["Authorization"] == "Bearer test-key-secret"

    def test_init_sets_content_type_header(self):
        """Test __init__ sets Content-Type header."""
        api = LambdaAPI("test-key")
        assert api.session.headers["Content-Type"] == "application/json"


class TestLambdaAPIRequestWithRetry:
    """Test LambdaAPI._request_with_retry method."""

    def test_request_with_retry_success_first_attempt(self, mocker):
        """Test _request_with_retry succeeds on first attempt."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_session = mocker.patch.object(api.session, "request", return_value=mock_response)

        result = api._request_with_retry("GET", "instances")

        assert result == mock_response
        mock_session.assert_called_once_with("GET", f"{api.BASE_URL}/instances")
        mock_response.raise_for_status.assert_called_once()

    def test_request_with_retry_passes_kwargs(self, mocker):
        """Test _request_with_retry passes kwargs to session.request."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_session = mocker.patch.object(api.session, "request", return_value=mock_response)

        payload = {"region": "us-west-1"}
        api._request_with_retry("POST", "instances", json=payload, timeout=30)

        mock_session.assert_called_once_with(
            "POST",
            f"{api.BASE_URL}/instances",
            json=payload,
            timeout=30
        )

    def test_request_with_retry_retries_on_failure(self, mocker):
        """Test _request_with_retry retries after failure."""
        api = LambdaAPI("test-key")

        # First call fails, second succeeds
        mock_failure = Mock()
        mock_failure.raise_for_status.side_effect = requests.exceptions.RequestException("Failure")

        mock_success = Mock()
        mock_success.raise_for_status = Mock()

        mock_session = mocker.patch.object(
            api.session,
            "request",
            side_effect=[mock_failure, mock_success]
        )
        mock_sleep = mocker.patch("time.sleep")

        result = api._request_with_retry("GET", "instances")

        assert result == mock_success
        assert mock_session.call_count == 2
        mock_sleep.assert_called_once_with(1)  # First retry delay

    def test_request_with_retry_exponential_backoff(self, mocker):
        """Test _request_with_retry uses exponential backoff."""
        api = LambdaAPI("test-key")

        # Fail twice, succeed on third
        mock_failure = Mock()
        mock_failure.raise_for_status.side_effect = requests.exceptions.RequestException("Failure")

        mock_success = Mock()
        mock_success.raise_for_status = Mock()

        mocker.patch.object(
            api.session,
            "request",
            side_effect=[mock_failure, mock_failure, mock_success]
        )
        mock_sleep = mocker.patch("time.sleep")

        api._request_with_retry("GET", "instances")

        # Verify exponential backoff delays: 1s, 2s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1  # First retry: 1s
        assert mock_sleep.call_args_list[1][0][0] == 2  # Second retry: 2s

    def test_request_with_retry_max_retries_exceeded(self, mocker):
        """Test _request_with_retry raises after max retries."""
        api = LambdaAPI("test-key")

        mock_failure = Mock()
        mock_failure.raise_for_status.side_effect = requests.exceptions.RequestException("Failure")

        mocker.patch.object(api.session, "request", return_value=mock_failure)
        mocker.patch("time.sleep")

        with pytest.raises(LambdaAPIError, match="API request failed after 3 attempts"):
            api._request_with_retry("GET", "instances")

    def test_request_with_retry_includes_original_error(self, mocker):
        """Test _request_with_retry includes original error in exception."""
        api = LambdaAPI("test-key")

        original_error = requests.exceptions.ConnectionError("Connection refused")
        mock_failure = Mock()
        mock_failure.raise_for_status.side_effect = original_error

        mocker.patch.object(api.session, "request", return_value=mock_failure)
        mocker.patch("time.sleep")

        with pytest.raises(LambdaAPIError, match="Connection refused"):
            api._request_with_retry("GET", "instances")


class TestLambdaAPIListInstances:
    """Test LambdaAPI.list_instances method."""

    def test_list_instances_success(self, mocker):
        """Test list_instances returns list of instances."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "instance-1",
                    "name": "my-instance",
                    "ip": "192.168.1.100",
                    "status": "active",
                    "instance_type": {"name": "gpu_1x_a100_sxm4_80gb"},
                    "region": {"name": "us-west-1"},
                    "created_at": "2025-01-01T10:00:00Z",
                },
                {
                    "id": "instance-2",
                    "status": "booting",
                    "instance_type": {"name": "gpu_1x_a10"},
                    "region": {"name": "us-east-1"},
                    "created_at": "2025-01-01T11:00:00Z",
                }
            ]
        }

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        instances = api.list_instances()

        assert len(instances) == 2
        assert instances[0].id == "instance-1"
        assert instances[0].name == "my-instance"
        assert instances[1].id == "instance-2"
        assert instances[1].name is None

    def test_list_instances_empty_data(self, mocker):
        """Test list_instances handles empty data."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {"data": []}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        instances = api.list_instances()

        assert instances == []

    def test_list_instances_missing_data_key(self, mocker):
        """Test list_instances handles missing data key."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        instances = api.list_instances()

        assert instances == []


class TestLambdaAPILaunchInstance:
    """Test LambdaAPI.launch_instance method."""

    def test_launch_instance_minimal_params(self, mocker):
        """Test launch_instance with minimal parameters."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"instance_ids": ["instance-123"]}
        }

        mock_request = mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        instance_id = api.launch_instance(
            region="us-west-1",
            instance_type="gpu_1x_a100_sxm4_80gb",
            ssh_key_names=["my-key"]
        )

        assert instance_id == "instance-123"
        mock_request.assert_called_once()

        # Verify payload
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert args[1] == "instance-operations/launch"
        assert kwargs["json"]["region_name"] == "us-west-1"
        assert kwargs["json"]["instance_type_name"] == "gpu_1x_a100_sxm4_80gb"
        assert kwargs["json"]["ssh_key_names"] == ["my-key"]

    def test_launch_instance_with_filesystem(self, mocker):
        """Test launch_instance with filesystem names."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"instance_ids": ["instance-123"]}
        }

        mock_request = mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        api.launch_instance(
            region="us-west-1",
            instance_type="gpu_1x_a10",
            ssh_key_names=["my-key"],
            filesystem_names=["my-filesystem"]
        )

        args, kwargs = mock_request.call_args
        assert kwargs["json"]["file_system_names"] == ["my-filesystem"]

    def test_launch_instance_with_name(self, mocker):
        """Test launch_instance with instance name."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"instance_ids": ["instance-123"]}
        }

        mock_request = mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        api.launch_instance(
            region="us-west-1",
            instance_type="gpu_1x_a10",
            ssh_key_names=["my-key"],
            name="my-instance"
        )

        args, kwargs = mock_request.call_args
        assert kwargs["json"]["name"] == "my-instance"

    def test_launch_instance_no_instance_id_returned(self, mocker):
        """Test launch_instance raises when no instance ID returned."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"instance_ids": []}
        }

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        with pytest.raises(LambdaAPIError, match="No instance ID returned from launch"):
            api.launch_instance(
                region="us-west-1",
                instance_type="gpu_1x_a10",
                ssh_key_names=["my-key"]
            )

    def test_launch_instance_returns_first_id(self, mocker):
        """Test launch_instance returns first ID when multiple returned."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"instance_ids": ["instance-1", "instance-2"]}
        }

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        instance_id = api.launch_instance(
            region="us-west-1",
            instance_type="gpu_1x_a10",
            ssh_key_names=["my-key"]
        )

        assert instance_id == "instance-1"


class TestLambdaAPITerminateInstance:
    """Test LambdaAPI.terminate_instance method."""

    def test_terminate_instance_success(self, mocker):
        """Test terminate_instance sends correct request."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_request = mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        api.terminate_instance("instance-123")

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert args[1] == "instance-operations/terminate"
        assert kwargs["json"]["instance_ids"] == ["instance-123"]

    def test_terminate_instance_no_return_value(self, mocker):
        """Test terminate_instance has no return value."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        result = api.terminate_instance("instance-123")

        assert result is None


class TestLambdaAPIGetInstance:
    """Test LambdaAPI.get_instance method."""

    def test_get_instance_found(self, mocker):
        """Test get_instance returns instance when found."""
        api = LambdaAPI("test-key")

        mock_instances = [
            Instance(
                id="instance-1",
                name="first",
                ip="192.168.1.100",
                status="active",
                instance_type="gpu_1x_a100_sxm4_80gb",
                region="us-west-1",
                created_at="2025-01-01T10:00:00Z"
            ),
            Instance(
                id="instance-2",
                name="second",
                ip="192.168.1.101",
                status="active",
                instance_type="gpu_1x_a10",
                region="us-east-1",
                created_at="2025-01-01T11:00:00Z"
            )
        ]

        mocker.patch.object(api, "list_instances", return_value=mock_instances)

        instance = api.get_instance("instance-2")

        assert instance is not None
        assert instance.id == "instance-2"
        assert instance.name == "second"

    def test_get_instance_not_found(self, mocker):
        """Test get_instance returns None when not found."""
        api = LambdaAPI("test-key")

        mock_instances = [
            Instance(
                id="instance-1",
                name="first",
                ip="192.168.1.100",
                status="active",
                instance_type="gpu_1x_a100_sxm4_80gb",
                region="us-west-1",
                created_at="2025-01-01T10:00:00Z"
            )
        ]

        mocker.patch.object(api, "list_instances", return_value=mock_instances)

        instance = api.get_instance("nonexistent-id")

        assert instance is None

    def test_get_instance_empty_list(self, mocker):
        """Test get_instance handles empty instance list."""
        api = LambdaAPI("test-key")

        mocker.patch.object(api, "list_instances", return_value=[])

        instance = api.get_instance("instance-123")

        assert instance is None


class TestLambdaAPIListSSHKeys:
    """Test LambdaAPI.list_ssh_keys method."""

    def test_list_ssh_keys_success(self, mocker):
        """Test list_ssh_keys returns list of key names."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"name": "key-1", "public_key": "ssh-rsa ..."},
                {"name": "key-2", "public_key": "ssh-rsa ..."},
                {"name": "key-3", "public_key": "ssh-rsa ..."}
            ]
        }

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        keys = api.list_ssh_keys()

        assert keys == ["key-1", "key-2", "key-3"]

    def test_list_ssh_keys_empty_data(self, mocker):
        """Test list_ssh_keys handles empty data."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {"data": []}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        keys = api.list_ssh_keys()

        assert keys == []

    def test_list_ssh_keys_missing_data_key(self, mocker):
        """Test list_ssh_keys handles missing data key."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        keys = api.list_ssh_keys()

        assert keys == []


class TestLambdaAPIListInstanceTypes:
    """Test LambdaAPI.list_instance_types method."""

    def test_list_instance_types_success(self, mocker):
        """Test list_instance_types returns list of InstanceType objects."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "gpu_1x_a100_sxm4_80gb": {
                    "instance_type": {
                        "description": "1x A100 SXM4 (80 GB)",
                        "price_cents_per_hour": 129,
                        "specs": {
                            "vcpus": 30,
                            "memory_gib": 200,
                            "storage_gib": 512,
                        }
                    },
                    "regions_with_capacity_available": [
                        {"name": "us-west-1"}
                    ]
                },
                "gpu_1x_a10": {
                    "instance_type": {
                        "description": "1x A10 (24 GB)",
                        "price_cents_per_hour": 60,
                        "specs": {
                            "vcpus": 30,
                            "memory_gib": 200,
                            "storage_gib": 512,
                        }
                    },
                    "regions_with_capacity_available": []
                }
            }
        }

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        types = api.list_instance_types()

        assert len(types) == 2
        assert any(t.name == "gpu_1x_a100_sxm4_80gb" for t in types)
        assert any(t.name == "gpu_1x_a10" for t in types)

        a100 = next(t for t in types if t.name == "gpu_1x_a100_sxm4_80gb")
        assert a100.price_cents_per_hour == 129
        assert a100.regions_available == ["us-west-1"]

    def test_list_instance_types_empty_data(self, mocker):
        """Test list_instance_types handles empty data."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {"data": {}}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        types = api.list_instance_types()

        assert types == []

    def test_list_instance_types_missing_data_key(self, mocker):
        """Test list_instance_types handles missing data key."""
        api = LambdaAPI("test-key")

        mock_response = Mock()
        mock_response.json.return_value = {}

        mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

        types = api.list_instance_types()

        assert types == []


class TestLambdaAPIGetInstanceType:
    """Test LambdaAPI.get_instance_type method."""

    def test_get_instance_type_found(self, mocker):
        """Test get_instance_type returns type when found."""
        api = LambdaAPI("test-key")

        mock_types = [
            InstanceType(
                name="gpu_1x_a100_sxm4_80gb",
                description="1x A100 SXM4 (80 GB)",
                price_cents_per_hour=129,
                vcpus=30,
                memory_gib=200,
                storage_gib=512,
                regions_available=["us-west-1"]
            ),
            InstanceType(
                name="gpu_1x_a10",
                description="1x A10 (24 GB)",
                price_cents_per_hour=60,
                vcpus=30,
                memory_gib=200,
                storage_gib=512,
                regions_available=[]
            )
        ]

        mocker.patch.object(api, "list_instance_types", return_value=mock_types)

        instance_type = api.get_instance_type("gpu_1x_a10")

        assert instance_type is not None
        assert instance_type.name == "gpu_1x_a10"
        assert instance_type.price_cents_per_hour == 60

    def test_get_instance_type_not_found(self, mocker):
        """Test get_instance_type returns None when not found."""
        api = LambdaAPI("test-key")

        mock_types = [
            InstanceType(
                name="gpu_1x_a100_sxm4_80gb",
                description="1x A100 SXM4 (80 GB)",
                price_cents_per_hour=129,
                vcpus=30,
                memory_gib=200,
                storage_gib=512,
                regions_available=["us-west-1"]
            )
        ]

        mocker.patch.object(api, "list_instance_types", return_value=mock_types)

        instance_type = api.get_instance_type("nonexistent-type")

        assert instance_type is None

    def test_get_instance_type_empty_list(self, mocker):
        """Test get_instance_type handles empty type list."""
        api = LambdaAPI("test-key")

        mocker.patch.object(api, "list_instance_types", return_value=[])

        instance_type = api.get_instance_type("gpu_1x_a10")

        assert instance_type is None
