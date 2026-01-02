# Testing Guide

This guide covers testing practices, running tests, and writing new tests for the soong CLI.

## Overview

The test suite uses **pytest** with coverage reporting, mocking, and HTTP request interception. Our goal is high coverage (95%+) with tests that verify actual behavior, not implementation details.

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py

# Run specific test
pytest tests/test_models.py::test_estimate_vram_llama_70b_int4

# Run tests matching pattern
pytest -k "vram"  # Runs all tests with "vram" in name
```

### Coverage Reporting

```bash
# Run with coverage
pytest --cov=soong

# Coverage with missing lines
pytest --cov=soong --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=soong --cov-report=html
# Open htmlcov/index.html in browser

# Coverage for specific module
pytest --cov=soong.models tests/test_models.py
```

### Test Output Options

```bash
# Show print statements
pytest -s

# Show logging output
pytest --log-cli-level=DEBUG

# Fail fast (stop on first failure)
pytest -x

# Run last failed tests
pytest --lf

# Run failed tests first, then all
pytest --ff
```

## Test Organization

### Directory Structure

```
cli/tests/
├── conftest.py                    # Shared fixtures
├── helpers/
│   ├── __init__.py
│   └── assertions.py              # Custom assertions
├── test_config.py                 # Configuration tests
├── test_models.py                 # Model registry tests
├── test_vram.py                   # VRAM estimation tests
├── test_gpu_recommendation.py     # GPU recommendation tests
├── test_lambda_api.py             # API client tests
├── test_instance.py               # Instance manager tests
├── test_ssh.py                    # SSH tunnel tests
├── test_history.py                # History tracking tests
├── test_cli_configure.py          # Configure command tests
├── test_cli_start.py              # Start command tests
├── test_cli_status.py             # Status command tests
├── test_cli_commands.py           # Other CLI commands
├── test_cli_models.py             # Models subcommand tests
├── test_cli_models_add.py         # Models add tests
├── test_cli_models_remove.py      # Models remove tests
└── test_cli_tunnel.py             # Tunnel subcommand tests
```

### Test Naming Conventions

From `conftest.py`:

```python
"""
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
```

## Writing Tests

### Unit Tests

Test individual functions in isolation:

```python
def test_estimate_vram_llama_70b_int4():
    """Test VRAM estimation for Llama 3.1 70B with INT4 quantization."""
    from soong.models import estimate_vram, Quantization

    result = estimate_vram(
        params_billions=70,
        quantization=Quantization.INT4,
        context_length=8192,
    )

    # Verify structure
    assert "base_vram_gb" in result
    assert "kv_cache_gb" in result
    assert "total_estimated_gb" in result
    assert "min_vram_gb" in result

    # Verify calculations
    # 70B * 0.5 bytes (INT4) = 35GB base
    assert result["base_vram_gb"] == 35.0

    # Total should be base + KV cache + overhead + activations
    assert result["total_estimated_gb"] > 35.0
    assert result["total_estimated_gb"] < 50.0  # Reasonable upper bound

    # Should fit on 48GB GPU
    assert result["min_vram_gb"] in [40, 48, 80]
```

### CLI Command Tests

Test CLI commands using `CliRunner`:

```python
def test_start_command_shows_cost_estimate(cli_runner, sample_config, mocker):
    """Test that start command shows cost estimate before launching."""
    # Setup mocks
    mocker.patch("soong.cli.get_config", return_value=sample_config)

    mock_api = mocker.Mock()
    mock_api.get_instance_type.return_value = mocker.Mock(
        description="1x A100 SXM4 (80 GB)",
        price_per_hour=1.29,
        estimate_cost=lambda h: 1.29 * h,
    )
    mocker.patch("soong.cli.LambdaAPI", return_value=mock_api)

    # Mock user declining
    mocker.patch("questionary.confirm", return_value=mocker.Mock(ask=lambda: False))

    # Run command
    result = cli_runner.invoke(app, ["start"])

    # Verify cost estimate shown
    assert "Cost Estimate" in result.output
    assert "$1.29/hr" in result.output
    assert "4 hours" in result.output  # Default lease

    # Verify launch cancelled
    assert "cancelled" in result.output.lower()
    assert result.exit_code == 0
```

### API Client Tests

Test API calls with `responses` library (not mocking `requests` directly):

```python
def test_list_instances_success(mock_http, lambda_api_base_url):
    """Test listing instances with successful API response."""
    # Setup mock HTTP response
    mock_http.add(
        responses.GET,
        f"{lambda_api_base_url}/instances",
        json={
            "data": [
                {
                    "id": "inst_abc123",
                    "name": "test-instance",
                    "ip": "1.2.3.4",
                    "status": "active",
                    "instance_type": {"name": "gpu_1x_a100_sxm4_80gb"},
                    "region": {"name": "us-west-1"},
                    "created_at": "2025-01-01T12:00:00Z",
                }
            ]
        },
        status=200,
    )

    # Call API
    from soong.lambda_api import LambdaAPI
    api = LambdaAPI("test_key")
    instances = api.list_instances()

    # Verify results
    assert len(instances) == 1
    assert instances[0].id == "inst_abc123"
    assert instances[0].status == "active"

    # Verify HTTP call made correctly
    assert len(mock_http.calls) == 1
    assert mock_http.calls[0].request.headers["Authorization"] == "Bearer test_key"
```

### Testing Error Handling

```python
def test_launch_instance_api_error(mock_http, lambda_api_base_url):
    """Test launch_instance handles API errors gracefully."""
    # Mock API error response
    mock_http.add(
        responses.POST,
        f"{lambda_api_base_url}/instance-operations/launch",
        json={"error": "Insufficient quota"},
        status=403,
    )

    # Call API and expect error
    from soong.lambda_api import LambdaAPI, LambdaAPIError
    api = LambdaAPI("test_key")

    with pytest.raises(LambdaAPIError, match="API request failed"):
        api.launch_instance(
            region="us-west-1",
            instance_type="gpu_1x_a100_sxm4_80gb",
            ssh_key_names=["my-key"],
        )
```

## Test Fixtures

### Common Fixtures (from `conftest.py`)

**Model configurations:**

```python
def test_using_sample_model(sample_model_config):
    """Use the sample 70B model fixture."""
    assert sample_model_config.params_billions == 70.0
    assert sample_model_config.default_quantization == Quantization.INT4

def test_using_small_model(small_model_config):
    """Use the sample 7B model fixture."""
    assert small_model_config.params_billions == 7.0
```

**Configuration:**

```python
def test_using_config(sample_config):
    """Use the sample configuration fixture."""
    assert sample_config.lambda_config.api_key == "test_key_12345"
    assert sample_config.defaults.lease_hours == 4
```

**HTTP mocking:**

```python
def test_api_call(mock_http, lambda_api_base_url):
    """Use HTTP mocking fixture."""
    mock_http.add(
        responses.GET,
        f"{lambda_api_base_url}/endpoint",
        json={"status": "ok"},
    )
    # Make request and verify
```

**CLI runner:**

```python
def test_command(cli_runner):
    """Use CLI runner fixture."""
    from soong.cli import app
    result = cli_runner.invoke(app, ["command", "args"])
    assert result.exit_code == 0
```

### Creating Custom Fixtures

```python
# In test file or conftest.py
import pytest

@pytest.fixture
def mock_instance_ready(mocker):
    """Mock an instance that is ready."""
    instance = mocker.Mock()
    instance.id = "inst_ready123"
    instance.status = "active"
    instance.ip = "5.6.7.8"
    return instance

def test_with_custom_fixture(mock_instance_ready):
    """Use custom fixture."""
    assert mock_instance_ready.status == "active"
```

## Mocking Best Practices

### Mock External Services, Not Internal Logic

**Good:**

```python
def test_instance_launch(mocker):
    """Mock the Lambda API, not internal logic."""
    mock_api = mocker.Mock()
    mock_api.launch_instance.return_value = "inst_123"

    manager = InstanceManager(mock_api)
    result = manager.launch_with_config(...)

    # Verify API was called correctly
    mock_api.launch_instance.assert_called_once_with(
        region="us-west-1",
        instance_type="gpu_1x_a100_sxm4_80gb",
    )
```

**Bad:**

```python
def test_instance_launch_bad(mocker):
    """Don't mock internal helper functions."""
    mocker.patch("soong.instance._validate_config")  # Internal detail
    # This test is brittle and doesn't verify behavior
```

### Use `responses` for HTTP, Not `mocker.patch("requests")`

**Good:**

```python
def test_http_request(mock_http):
    """Mock HTTP responses with responses library."""
    mock_http.add(responses.GET, "https://api.example.com", json={"ok": True})

    result = requests.get("https://api.example.com")
    assert result.json()["ok"] is True
```

**Bad:**

```python
def test_http_request_bad(mocker):
    """Don't mock requests directly."""
    mocker.patch("requests.get", return_value=mocker.Mock(json=lambda: {"ok": True}))
    # Doesn't test actual HTTP logic
```

### Use Realistic Test Data

**Good:**

```python
def test_instance_parsing(mock_http):
    """Use realistic instance data from Lambda API."""
    mock_http.add(
        responses.GET,
        url,
        json={
            "data": [
                {
                    "id": "inst_unique_789xyz",  # Unique ID
                    "name": "my-test-instance",
                    "ip": "192.168.99.42",  # Unique IP
                    "status": "active",
                    # ... full realistic data
                }
            ]
        },
    )
```

**Bad:**

```python
def test_instance_parsing_bad(mock_http):
    """Don't use minimal data that hides bugs."""
    mock_http.add(responses.GET, url, json={"data": [{"id": "123"}]})
    # Missing fields would cause AttributeError in real usage
```

## Coverage Goals

### Current Coverage

As of recent updates, the test suite achieves:

- **Overall coverage**: 95%+
- **Core modules**: 95-100%
- **CLI commands**: 90-95%
- **API client**: 95%+

### Measuring Coverage

```bash
# Generate coverage report
pytest --cov=soong --cov-report=term-missing

# See which lines are not covered
pytest --cov=soong --cov-report=html
open htmlcov/index.html
```

### Improving Coverage

**Find untested code:**

```bash
pytest --cov=soong --cov-report=term-missing | grep -A 5 "TOTAL"
```

**Add tests for uncovered lines:**

```python
# Example: Testing error path
def test_config_validation_invalid_quantization():
    """Test that invalid quantization raises ValueError."""
    from soong.config import validate_custom_model

    invalid_model = {
        "hf_path": "org/model",
        "params_billions": 7,
        "quantization": "invalid",  # Invalid value
        "context_length": 8192,
    }

    with pytest.raises(ValueError, match="Invalid quantization"):
        validate_custom_model(invalid_model)
```

## Continuous Integration

Tests run automatically on:

- Every push to feature branches
- Every pull request
- Merges to main branch

### CI Configuration

GitHub Actions workflow (`.github/workflows/test.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          cd cli
          pip install -e ".[test]"

      - name: Run tests with coverage
        run: |
          cd cli
          pytest --cov=soong --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./cli/coverage.xml
```

## Debugging Tests

### Using `pytest --pdb`

```bash
# Drop into debugger on failure
pytest --pdb tests/test_models.py

# Drop into debugger on first failure
pytest -x --pdb
```

### Adding Breakpoints

```python
def test_complex_logic():
    """Test with debugging."""
    result = complex_function()

    import pdb; pdb.set_trace()  # Debugger stops here

    assert result == expected
```

### Viewing Test Output

```bash
# Show all print statements
pytest -s

# Show logging
pytest --log-cli-level=DEBUG

# Capture turned off (shows all output)
pytest --capture=no
```

## Test Performance

### Running Tests Quickly

```bash
# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto

# Run only fast tests (mark slow tests with @pytest.mark.slow)
pytest -m "not slow"

# Run only changed tests
pytest --testmon
```

### Marking Slow Tests

```python
import pytest

@pytest.mark.slow
def test_full_integration_workflow():
    """This test takes >5 seconds."""
    # Slow integration test
```

Then skip slow tests:

```bash
pytest -m "not slow"
```

## Testing Best Practices

### 1. Test Behavior, Not Implementation

**Good:**

```python
def test_launch_instance_creates_active_instance():
    """Verify instance becomes active after launch."""
    # Test the outcome
    assert instance.status == "active"
```

**Bad:**

```python
def test_launch_instance_calls_api_exactly_once():
    """Don't test implementation details."""
    # Too coupled to implementation
    mock_api.launch_instance.assert_called_once()
```

### 2. Use Descriptive Test Names

**Good:**

```python
def test_estimate_vram_70b_int4_fits_on_a100_80gb():
    """Clear what is being tested and expected outcome."""
```

**Bad:**

```python
def test_vram():
    """Vague and unhelpful."""
```

### 3. Arrange-Act-Assert Pattern

```python
def test_something():
    # Arrange: Set up test data
    model = ModelConfig(...)

    # Act: Execute the code being tested
    result = model.estimated_vram_gb

    # Assert: Verify the outcome
    assert result > 0
    assert result < 100
```

### 4. One Logical Assertion Per Test

**Good:**

```python
def test_vram_estimate_includes_base():
    """Test that base VRAM is calculated."""
    assert result["base_vram_gb"] == 35.0

def test_vram_estimate_includes_overhead():
    """Test that overhead is included."""
    assert result["total_estimated_gb"] > result["base_vram_gb"]
```

**Bad:**

```python
def test_vram_estimate():
    """Test everything at once."""
    assert result["base_vram_gb"] == 35.0
    assert result["kv_cache_gb"] > 0
    assert result["overhead_gb"] == 2.0
    assert result["total_estimated_gb"] > 35.0
    # Hard to debug when one assertion fails
```

### 5. Test Edge Cases

```python
def test_estimate_vram_zero_params():
    """Test VRAM estimation with zero parameters."""
    result = estimate_vram(0, Quantization.FP16, 8192)
    assert result["base_vram_gb"] == 0

def test_estimate_vram_huge_params():
    """Test VRAM estimation with very large model."""
    result = estimate_vram(1000, Quantization.FP32, 32768)
    assert result["min_vram_gb"] == 160  # Multi-GPU
```

## Next Steps

- Read [Development Setup](development-setup.md) to set up your environment
- Explore existing tests in `cli/tests/`
- Run tests and experiment with changes
- Write tests for new features before implementing them (TDD)
