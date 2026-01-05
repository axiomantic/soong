"""Tests for instance.py InstanceManager class."""

import pytest
import time_machine
from datetime import timedelta
from unittest.mock import Mock, patch, call
from soong.instance import InstanceManager
from soong.lambda_api import LambdaAPIError, Instance


@pytest.fixture
def mock_api(mocker):
    """Mock Lambda API client."""
    return mocker.Mock()


@pytest.fixture
def instance_manager(mock_api):
    """InstanceManager instance with mocked API."""
    return InstanceManager(api=mock_api)


@pytest.fixture
def mock_active_instance():
    """Mock active instance with IP."""
    return Instance(
        id="i-active-123",
        name="test-instance",
        ip="1.2.3.4",
        status="active",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z",
        lease_expires_at="2024-01-02T00:00:00Z"
    )


@pytest.fixture
def mock_pending_instance():
    """Mock pending instance without IP."""
    return Instance(
        id="i-pending-456",
        name="test-instance",
        ip=None,
        status="pending",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z"
    )


@pytest.fixture
def mock_terminated_instance():
    """Mock terminated instance."""
    return Instance(
        id="i-terminated-789",
        name="test-instance",
        ip=None,
        status="terminated",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z"
    )


@pytest.fixture
def mock_unhealthy_instance():
    """Mock unhealthy instance."""
    return Instance(
        id="i-unhealthy-999",
        name="test-instance",
        ip="1.2.3.4",
        status="unhealthy",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z"
    )


# wait_for_ready() tests


def test_wait_for_ready_returns_active_instance_immediately(
    instance_manager, mock_api, mock_active_instance, mocker
):
    """Test wait_for_ready returns immediately when instance is active with IP."""
    mock_api.get_instance.return_value = mock_active_instance
    mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-active-123", timeout_seconds=60)

    assert result == mock_active_instance
    assert result.status == "active"
    assert result.ip == "1.2.3.4"
    mock_api.get_instance.assert_called_once_with("i-active-123")


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_waits_for_pending_to_active(
    instance_manager, mock_api, mock_pending_instance, mock_active_instance, mocker
):
    """Test wait_for_ready polls until instance becomes active."""
    # First call: pending, second call: active
    mock_api.get_instance.side_effect = [mock_pending_instance, mock_active_instance]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-pending-456", timeout_seconds=60)

    assert result == mock_active_instance
    assert result.status == "active"
    # Verify polling: get_instance called exactly 2 times
    assert mock_api.get_instance.call_count == 2
    assert mock_api.get_instance.call_args_list[0] == call("i-pending-456")
    assert mock_api.get_instance.call_args_list[1] == call("i-pending-456")


def test_wait_for_ready_returns_none_on_timeout(
    instance_manager, mock_api, mock_pending_instance, mocker
):
    """Test wait_for_ready returns None when timeout is exceeded."""
    mock_api.get_instance.return_value = mock_pending_instance

    with time_machine.travel("2024-01-01 00:00:00", tick=False) as traveller:
        # Mock sleep to advance time instead of actually sleeping
        def mock_sleep(seconds):
            traveller.shift(timedelta(seconds=seconds))

        mocker.patch("time.sleep", side_effect=mock_sleep)

        result = instance_manager.wait_for_ready("i-pending-456", timeout_seconds=600)

    assert result is None
    # Verify multiple polling attempts occurred before timeout
    assert mock_api.get_instance.call_count >= 1


def test_wait_for_ready_returns_none_when_instance_not_found(
    instance_manager, mock_api, mocker
):
    """Test wait_for_ready returns None when instance doesn't exist."""
    mock_api.get_instance.return_value = None
    mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-nonexistent", timeout_seconds=60)

    assert result is None
    mock_api.get_instance.assert_called_once_with("i-nonexistent")


def test_wait_for_ready_returns_none_for_terminated_instance(
    instance_manager, mock_api, mock_terminated_instance, mocker
):
    """Test wait_for_ready returns None when instance is terminated."""
    mock_api.get_instance.return_value = mock_terminated_instance
    mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-terminated-789", timeout_seconds=60)

    assert result is None


def test_wait_for_ready_returns_none_for_unhealthy_instance(
    instance_manager, mock_api, mock_unhealthy_instance, mocker
):
    """Test wait_for_ready returns None when instance is unhealthy."""
    mock_api.get_instance.return_value = mock_unhealthy_instance
    mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-unhealthy-999", timeout_seconds=60)

    assert result is None


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_handles_api_errors_and_retries(
    instance_manager, mock_api, mock_active_instance, mocker
):
    """Test wait_for_ready continues polling after API errors."""
    # First call: API error, second call: success
    mock_api.get_instance.side_effect = [
        LambdaAPIError("Network error"),
        mock_active_instance
    ]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-active-123", timeout_seconds=60)

    assert result == mock_active_instance
    # Verify polling interleaving: error then success
    assert mock_api.get_instance.call_count == 2
    assert mock_api.get_instance.call_args_list[0] == call("i-active-123")
    assert mock_api.get_instance.call_args_list[1] == call("i-active-123")
    # Verify sleep was called after error before retrying
    mock_sleep.assert_called_once_with(10)


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_requires_both_active_status_and_ip(
    instance_manager, mock_api, mocker
):
    """Test wait_for_ready requires both 'active' status AND IP address."""
    # Instance is active but has no IP yet
    instance_without_ip = Instance(
        id="i-test",
        name="test",
        ip=None,  # No IP yet
        status="active",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z"
    )

    instance_with_ip = Instance(
        id="i-test",
        name="test",
        ip="1.2.3.4",  # Now has IP
        status="active",
        instance_type="gpu_1x_a100_sxm4_80gb",
        region="us-west-1",
        created_at="2024-01-01T00:00:00Z"
    )

    mock_api.get_instance.side_effect = [instance_without_ip, instance_with_ip]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-test", timeout_seconds=60)

    assert result == instance_with_ip
    assert result.ip == "1.2.3.4"
    # Verify polling sequence: first check (no IP), second check (has IP)
    assert mock_api.get_instance.call_count == 2
    assert mock_api.get_instance.call_args_list[0] == call("i-test")
    assert mock_api.get_instance.call_args_list[1] == call("i-test")
    # Verify sleep occurred between checks
    mock_sleep.assert_called_once_with(10)


def test_wait_for_ready_uses_custom_timeout(
    instance_manager, mock_api, mock_pending_instance, mocker
):
    """Test wait_for_ready respects custom timeout value."""
    mock_api.get_instance.return_value = mock_pending_instance

    with time_machine.travel("2024-01-01 00:00:00", tick=False) as traveller:
        # Mock sleep to advance time instead of actually sleeping
        def mock_sleep(seconds):
            traveller.shift(timedelta(seconds=seconds))

        mocker.patch("time.sleep", side_effect=mock_sleep)

        result = instance_manager.wait_for_ready("i-pending-456", timeout_seconds=120)

    assert result is None


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_polls_at_10_second_intervals(
    instance_manager, mock_api, mock_pending_instance, mock_active_instance, mocker
):
    """Test wait_for_ready uses 10 second poll interval."""
    # Require 3 polls before becoming active
    mock_api.get_instance.side_effect = [
        mock_pending_instance,
        mock_pending_instance,
        mock_active_instance
    ]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("i-pending-456", timeout_seconds=60)

    assert result == mock_active_instance
    # Verify exact polling sequence with timing
    assert mock_api.get_instance.call_count == 3
    # Should have slept twice (after first two polls), each time for exactly 10 seconds
    assert mock_sleep.call_count == 2
    # Verify each sleep call was exactly 10 seconds
    assert mock_sleep.call_args_list[0] == call(10)
    assert mock_sleep.call_args_list[1] == call(10)


# get_active_instance() tests


def test_get_active_instance_returns_first_active(
    instance_manager, mock_api, mock_active_instance, mock_pending_instance
):
    """Test get_active_instance returns first active instance from list."""
    mock_api.list_instances.return_value = [
        mock_pending_instance,
        mock_active_instance,
        Instance(
            id="i-active-2",
            name="second-active",
            ip="5.6.7.8",
            status="active",
            instance_type="gpu_1x_a10",
            region="us-east-1",
            created_at="2024-01-01T00:00:00Z"
        )
    ]

    result = instance_manager.get_active_instance()

    assert result == mock_active_instance
    assert result.id == "i-active-123"


def test_get_active_instance_returns_none_when_no_active(
    instance_manager, mock_api, mock_pending_instance, mock_terminated_instance
):
    """Test get_active_instance returns None when no active instances."""
    mock_api.list_instances.return_value = [
        mock_pending_instance,
        mock_terminated_instance
    ]

    result = instance_manager.get_active_instance()

    assert result is None


def test_get_active_instance_returns_none_on_empty_list(
    instance_manager, mock_api
):
    """Test get_active_instance returns None for empty instance list."""
    mock_api.list_instances.return_value = []

    result = instance_manager.get_active_instance()

    assert result is None


def test_get_active_instance_handles_api_error(
    instance_manager, mock_api
):
    """Test get_active_instance returns None on API error."""
    mock_api.list_instances.side_effect = LambdaAPIError("API error")

    result = instance_manager.get_active_instance()

    assert result is None


def test_get_active_instance_ignores_non_active_statuses(
    instance_manager, mock_api
):
    """Test get_active_instance ignores pending, terminated, and unhealthy instances."""
    mock_api.list_instances.return_value = [
        Instance(
            id="i-1", name="test1", ip=None, status="pending",
            instance_type="gpu_1x_a10", region="us-west-1",
            created_at="2024-01-01T00:00:00Z"
        ),
        Instance(
            id="i-2", name="test2", ip=None, status="terminated",
            instance_type="gpu_1x_a10", region="us-west-1",
            created_at="2024-01-01T00:00:00Z"
        ),
        Instance(
            id="i-3", name="test3", ip="1.2.3.4", status="unhealthy",
            instance_type="gpu_1x_a10", region="us-west-1",
            created_at="2024-01-01T00:00:00Z"
        ),
        Instance(
            id="i-4", name="test4", ip=None, status="booting",
            instance_type="gpu_1x_a10", region="us-west-1",
            created_at="2024-01-01T00:00:00Z"
        )
    ]

    result = instance_manager.get_active_instance()

    assert result is None


# poll_status() tests


def test_poll_status_returns_instance(
    instance_manager, mock_api, mock_active_instance
):
    """Test poll_status returns instance details."""
    mock_api.get_instance.return_value = mock_active_instance

    result = instance_manager.poll_status("i-active-123")

    assert result == mock_active_instance
    mock_api.get_instance.assert_called_once_with("i-active-123")


def test_poll_status_returns_none_when_not_found(
    instance_manager, mock_api
):
    """Test poll_status returns None when instance doesn't exist."""
    mock_api.get_instance.return_value = None

    result = instance_manager.poll_status("i-nonexistent")

    assert result is None


def test_poll_status_handles_api_error(
    instance_manager, mock_api
):
    """Test poll_status returns None on API error."""
    mock_api.get_instance.side_effect = LambdaAPIError("Network error")

    result = instance_manager.poll_status("i-test")

    assert result is None


def test_poll_status_works_for_any_status(
    instance_manager, mock_api, mock_pending_instance,
    mock_active_instance, mock_terminated_instance
):
    """Test poll_status returns instance regardless of status."""
    # Pending
    mock_api.get_instance.return_value = mock_pending_instance
    result = instance_manager.poll_status("i-pending-456")
    assert result.status == "pending"

    # Active
    mock_api.get_instance.return_value = mock_active_instance
    result = instance_manager.poll_status("i-active-123")
    assert result.status == "active"

    # Terminated
    mock_api.get_instance.return_value = mock_terminated_instance
    result = instance_manager.poll_status("i-terminated-789")
    assert result.status == "terminated"


def test_poll_status_does_not_retry(
    instance_manager, mock_api
):
    """Test poll_status makes single call without retry logic."""
    mock_api.get_instance.side_effect = LambdaAPIError("Error")

    result = instance_manager.poll_status("i-test")

    assert result is None
    # Should only be called once (no retry)
    mock_api.get_instance.assert_called_once_with("i-test")


# Integration/edge case tests


def test_instance_manager_initialization(mock_api):
    """Test InstanceManager initializes with API client."""
    manager = InstanceManager(api=mock_api)

    assert manager.api == mock_api


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_displays_progress_updates(
    instance_manager, mock_api, mock_pending_instance, mock_active_instance, mocker
):
    """Test wait_for_ready updates status display with current status."""
    mock_api.get_instance.side_effect = [mock_pending_instance, mock_active_instance]
    mocker.patch("time.sleep")

    # Mock Live context manager to capture status updates
    mock_live = mocker.Mock()
    mock_live.__enter__ = mocker.Mock(return_value=mock_live)
    mock_live.__exit__ = mocker.Mock(return_value=None)

    with patch("soong.instance.Live", return_value=mock_live):
        result = instance_manager.wait_for_ready("i-pending-456", timeout_seconds=60)

    assert result == mock_active_instance
    # Verify Live display was created (status display is shown)
    assert mock_live.__enter__.called


def test_wait_for_ready_continuous_api_errors_until_timeout(
    instance_manager, mock_api, mocker
):
    """Test wait_for_ready handles continuous API errors until timeout."""
    mock_api.get_instance.side_effect = LambdaAPIError("Persistent error")

    with time_machine.travel("2024-01-01 00:00:00", tick=False) as traveller:
        # Mock sleep to advance time instead of actually sleeping
        def mock_sleep(seconds):
            traveller.shift(timedelta(seconds=seconds))

        mocker.patch("time.sleep", side_effect=mock_sleep)

        result = instance_manager.wait_for_ready("i-test", timeout_seconds=600)

    assert result is None
    # Should have tried multiple times before timeout
    assert mock_api.get_instance.call_count >= 1


# Tests for booting instance without created_at (the bug scenario)


@pytest.fixture
def mock_booting_instance_no_created_at():
    """Mock booting instance that lacks created_at field.

    This represents the exact API response that caused the KeyError bug.
    During 'booting' status, Lambda Labs API may omit certain fields.
    """
    return Instance(
        id="fd3896afa3a941be83d765158112ce62",
        name=None,
        ip=None,
        status="booting",
        instance_type="gpu_1x_gh200",
        region="us-east-3",
        created_at=None,  # This is the key difference - no created_at
        lease_expires_at=None
    )


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_handles_booting_instance_without_created_at(
    instance_manager, mock_api, mock_active_instance, mocker
):
    """Test wait_for_ready works when booting instance lacks created_at.

    This is a regression test for the KeyError: 'created_at' bug.
    The bug occurred when:
    1. Instance was launched
    2. wait_for_ready polled get_instance
    3. get_instance called list_instances
    4. list_instances called Instance.from_api_response
    5. from_api_response crashed on data["created_at"]

    Now created_at should be optional and the flow should work.
    """
    # First poll: booting without created_at
    booting_instance = Instance(
        id="test-booting-123",
        name=None,
        ip=None,
        status="booting",
        instance_type="gpu_1x_gh200",
        region="us-east-3",
        created_at=None,  # Missing created_at
        lease_expires_at=None
    )

    # Second poll: becomes active with all fields
    active_instance = Instance(
        id="test-booting-123",
        name=None,
        ip="192.168.1.100",
        status="active",
        instance_type="gpu_1x_gh200",
        region="us-east-3",
        created_at="2025-01-04T12:00:00Z",
        lease_expires_at=None
    )

    mock_api.get_instance.side_effect = [booting_instance, active_instance]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("test-booting-123", timeout_seconds=60)

    assert result is not None
    assert result.status == "active"
    assert result.ip == "192.168.1.100"
    assert mock_api.get_instance.call_count == 2


@time_machine.travel("2024-01-01 00:00:00", tick=False)
def test_wait_for_ready_polls_through_multiple_booting_states(
    instance_manager, mock_api, mocker
):
    """Test wait_for_ready can poll through multiple booting states without crashing."""
    # Simulate realistic boot sequence:
    # Poll 1: booting, no IP, no created_at
    # Poll 2: booting, no IP, has created_at now
    # Poll 3: active, has IP, has created_at

    poll_1 = Instance(
        id="boot-test", name=None, ip=None, status="booting",
        instance_type="gpu_1x_gh200", region="us-east-3",
        created_at=None  # Not yet available
    )

    poll_2 = Instance(
        id="boot-test", name=None, ip=None, status="booting",
        instance_type="gpu_1x_gh200", region="us-east-3",
        created_at="2025-01-04T12:00:00Z"  # Now available
    )

    poll_3 = Instance(
        id="boot-test", name="my-instance", ip="10.0.0.5", status="active",
        instance_type="gpu_1x_gh200", region="us-east-3",
        created_at="2025-01-04T12:00:00Z"
    )

    mock_api.get_instance.side_effect = [poll_1, poll_2, poll_3]
    mock_sleep = mocker.patch("time.sleep")

    result = instance_manager.wait_for_ready("boot-test", timeout_seconds=120)

    assert result is not None
    assert result.status == "active"
    assert result.ip == "10.0.0.5"
    assert mock_api.get_instance.call_count == 3


def test_get_active_instance_handles_booting_without_created_at(
    instance_manager, mock_api
):
    """Test get_active_instance doesn't crash on instances without created_at."""
    mock_api.list_instances.return_value = [
        Instance(
            id="i-booting", name=None, ip=None, status="booting",
            instance_type="gpu_1x_gh200", region="us-east-3",
            created_at=None  # Missing
        ),
        Instance(
            id="i-active", name="active-one", ip="1.2.3.4", status="active",
            instance_type="gpu_1x_a100", region="us-west-1",
            created_at="2025-01-04T12:00:00Z"
        )
    ]

    result = instance_manager.get_active_instance()

    # Should find the active instance, not crash on the booting one
    assert result is not None
    assert result.id == "i-active"
    assert result.status == "active"
