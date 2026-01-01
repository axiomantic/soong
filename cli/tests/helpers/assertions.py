"""Test assertion helpers to eliminate Green Mirage patterns.

These helpers enforce rigorous assertions that would fail if production
code is broken, avoiding the patterns identified in the Green Mirage audit:

Pattern #1: Existence vs Validity - Use assert_configured_object
Pattern #2: Partial Assertions - Use assert_table_row, assert_exact_output
Pattern #3: Shallow String Matching - Use assert_hf_path_valid, assert_exact_match
Pattern #4: Lack of Consumption - Use assert_json_consumed, assert_response_used
Pattern #5: Mocking Reality Away - Use responses library (see conftest fixtures)
Pattern #6: Swallowed Errors - Test each exception path explicitly
Pattern #7: State Mutation - Use assert_state_transition
Pattern #8: Incomplete Branch Coverage - Test both bounds, all branches
"""

from typing import Any, Callable, Optional
from unittest.mock import Mock


def assert_exact_command(actual: list, expected: list) -> None:
    """Assert command arrays match exactly (Pattern #2, #3 fix).

    Args:
        actual: The command array that was executed
        expected: The expected command array

    Raises:
        AssertionError: If commands don't match exactly
    """
    assert actual == expected, (
        f"Command mismatch:\n"
        f"Expected: {expected}\n"
        f"Actual:   {actual}"
    )


def assert_table_row(stdout: str, **expected_values) -> str:
    """Assert table output contains row with all expected values in same line (Pattern #2 fix).

    This prevents false positives where keywords appear in output but in wrong
    context (e.g., error messages instead of data rows).

    Args:
        stdout: The captured stdout from CLI
        **expected_values: Key-value pairs that must all appear in the same line

    Returns:
        The matching line for further assertions

    Raises:
        AssertionError: If no row contains all expected values
    """
    lines = stdout.split('\n')
    for line in lines:
        if all(str(v) in line for v in expected_values.values()):
            return line
    raise AssertionError(
        f"No row found with all values: {expected_values}\n"
        f"Output was:\n{stdout}"
    )


def assert_no_error_keywords(stdout: str) -> None:
    """Assert output doesn't contain error indicators (Pattern #2 fix).

    Prevents false positives where expected keywords appear in error context.

    Args:
        stdout: The captured stdout from CLI

    Raises:
        AssertionError: If error keywords found in output
    """
    error_keywords = ['error', 'failed', 'exception', 'traceback', 'fatal']
    lower = stdout.lower()
    for keyword in error_keywords:
        # Allow "error" in column headers or expected contexts
        if keyword in lower and f'no {keyword}' not in lower:
            # Check if it's in an actual error context
            lines_with_keyword = [
                line for line in stdout.split('\n')
                if keyword in line.lower()
            ]
            for line in lines_with_keyword:
                # Skip if it's a header or label
                if not any(header in line.lower() for header in ['column', 'header', 'field']):
                    raise AssertionError(
                        f"Error keyword '{keyword}' found in output:\n{line}"
                    )


def assert_json_consumed(mock_response: Mock, expected_calls: int = 1) -> None:
    """Assert response.json() was called expected number of times (Pattern #4 fix).

    This verifies that the code actually consumed the response data rather than
    hardcoding values or ignoring the response.

    Args:
        mock_response: The mocked response object
        expected_calls: Number of times json() should have been called

    Raises:
        AssertionError: If json() call count doesn't match
    """
    actual_calls = mock_response.json.call_count
    assert actual_calls == expected_calls, (
        f"response.json() called {actual_calls} times, expected {expected_calls}. "
        f"This may indicate the code is not consuming the response data."
    )


def assert_response_used(mock_response: Mock, expected_value: Any, actual_value: Any) -> None:
    """Assert that a value came from the mocked response, not hardcoded (Pattern #4 fix).

    Use different values in mock vs what would be hardcoded to prove consumption.

    Args:
        mock_response: The mocked response object
        expected_value: The value set in the mock that should appear in output
        actual_value: The actual value from the function under test

    Raises:
        AssertionError: If values don't match or json() wasn't called
    """
    assert_json_consumed(mock_response, expected_calls=1)
    assert actual_value == expected_value, (
        f"Value mismatch - suggests response not consumed:\n"
        f"Expected (from mock): {expected_value}\n"
        f"Actual: {actual_value}"
    )


def assert_state_transition(
    get_state_fn: Callable[[], Any],
    expected_before: Any,
    expected_after: Any,
    action_fn: Callable[[], Any],
) -> Any:
    """Assert state changes correctly from before to after action (Pattern #7 fix).

    Args:
        get_state_fn: Function to get current state
        expected_before: Expected state before action
        expected_after: Expected state after action
        action_fn: Function that performs the state-changing action

    Returns:
        The result of action_fn

    Raises:
        AssertionError: If state doesn't match expected before or after
    """
    before = get_state_fn()
    assert before == expected_before, (
        f"Initial state wrong:\n"
        f"Expected: {expected_before}\n"
        f"Actual: {before}"
    )

    result = action_fn()

    after = get_state_fn()
    assert after == expected_after, (
        f"Final state wrong:\n"
        f"Expected: {expected_after}\n"
        f"Actual: {after}"
    )

    return result


def assert_hf_path_valid(hf_path: str, expected_org: Optional[str] = None) -> None:
    """Assert HuggingFace path has valid format (Pattern #3 fix).

    Args:
        hf_path: The HuggingFace path to validate (e.g., "deepseek-ai/model-name")
        expected_org: If provided, the expected organization prefix

    Raises:
        AssertionError: If path format is invalid
    """
    parts = hf_path.split("/")
    assert len(parts) == 2, (
        f"HF path must have org/model format, got: {hf_path}"
    )
    assert parts[0], f"HF path organization is empty: {hf_path}"
    assert parts[1], f"HF path model name is empty: {hf_path}"

    if expected_org:
        assert parts[0] == expected_org, (
            f"Expected organization '{expected_org}', got '{parts[0]}' in path: {hf_path}"
        )


def assert_configured_object(obj: Any, **expected_attrs) -> None:
    """Assert object exists AND has correct configuration (Pattern #1 fix).

    This goes beyond isinstance checks to verify actual configuration.

    Args:
        obj: The object to check
        **expected_attrs: Attribute name-value pairs to verify

    Raises:
        AssertionError: If object is None or attributes don't match
    """
    assert obj is not None, "Object is None"

    for attr_name, expected_value in expected_attrs.items():
        if '.' in attr_name:
            # Handle nested attributes like "headers.Authorization"
            parts = attr_name.split('.')
            current = obj
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = getattr(current, part, None)
            actual_value = current
        else:
            actual_value = getattr(obj, attr_name, None)

        assert actual_value == expected_value, (
            f"Attribute '{attr_name}' mismatch:\n"
            f"Expected: {expected_value}\n"
            f"Actual: {actual_value}"
        )


def assert_ssh_command(
    call_args: list,
    expected_user: str,
    expected_host: str,
    expected_key_path: Optional[str] = None,
    expected_port_forwards: Optional[list] = None,
) -> None:
    """Assert SSH command structure is correct (Pattern #5 fix for SSH tests).

    Args:
        call_args: The command array passed to subprocess
        expected_user: Expected SSH username
        expected_host: Expected target host
        expected_key_path: If provided, expected identity file path
        expected_port_forwards: List of port forward specs like "8000:localhost:8000"

    Raises:
        AssertionError: If command structure is wrong
    """
    assert call_args[0] == "ssh", f"First arg should be 'ssh', got: {call_args[0]}"

    # Check user@host format
    target = f"{expected_user}@{expected_host}"
    assert target in call_args, (
        f"SSH target '{target}' not found in command: {call_args}"
    )

    if expected_key_path:
        assert "-i" in call_args, "Missing -i flag for identity file"
        key_idx = call_args.index("-i")
        assert call_args[key_idx + 1] == expected_key_path, (
            f"Wrong key path: expected {expected_key_path}, got {call_args[key_idx + 1]}"
        )

    if expected_port_forwards:
        for port_forward in expected_port_forwards:
            assert "-L" in call_args, "Missing -L flag for port forwarding"
            assert port_forward in call_args, (
                f"Port forward '{port_forward}' not found in command: {call_args}"
            )


def assert_bounds(
    value: float,
    min_bound: float,
    max_bound: float,
    value_name: str = "value",
) -> None:
    """Assert value is within both lower and upper bounds (Pattern #8 fix).

    Args:
        value: The value to check
        min_bound: Minimum allowed value (inclusive)
        max_bound: Maximum allowed value (inclusive)
        value_name: Name for error messages

    Raises:
        AssertionError: If value is outside bounds
    """
    assert value >= min_bound, (
        f"{value_name} {value} is below minimum {min_bound}"
    )
    assert value <= max_bound, (
        f"{value_name} {value} exceeds maximum {max_bound}"
    )


def assert_optimal_selection(
    selected: str,
    viable_options: list,
    cost_key: Callable[[str], float],
    requirement_check: Callable[[str], bool],
) -> None:
    """Assert the cheapest viable option was selected (Pattern #8 fix).

    Args:
        selected: The selected option
        viable_options: All options that could have been selected
        cost_key: Function to get cost of an option
        requirement_check: Function that returns True if option meets requirements

    Raises:
        AssertionError: If a cheaper viable option exists
    """
    # Filter to viable options
    viable = [opt for opt in viable_options if requirement_check(opt)]
    assert selected in viable, (
        f"Selected option '{selected}' does not meet requirements"
    )

    # Find cheapest
    cheapest = min(viable, key=cost_key)
    assert selected == cheapest, (
        f"Selected '{selected}' but '{cheapest}' is cheaper and viable"
    )
