# Development Setup

This guide walks you through setting up a local development environment for soong CLI.

## Prerequisites

### Required

- **Python 3.10 or higher**
  ```bash
  python3 --version  # Should be 3.10+
  ```

- **Git**
  ```bash
  git --version
  ```

- **pip** (usually comes with Python)
  ```bash
  pip --version
  ```

### Optional

- **Lambda Labs account** (for testing against real API)
- **SSH key** configured in Lambda Labs
- **Lambda filesystem** named `coding-stack`

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/axiomantic/soong.git
cd my-ai/cli
```

Or if you're forking:

```bash
git clone https://github.com/YOUR_USERNAME/my-ai.git
cd my-ai/cli
git remote add upstream https://github.com/axiomantic/soong.git
```

### 2. Create Virtual Environment

Using `venv` (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

On Windows:

```cmd
python -m venv venv
venv\Scripts\activate
```

On Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

Install the package in editable mode with test dependencies:

```bash
pip install -e ".[test]"
```

This installs:

- **Runtime dependencies**: typer, rich, requests, pyyaml, questionary
- **Test dependencies**: pytest, pytest-cov, pytest-mock, responses

### 4. Verify Installation

```bash
# Check that CLI is available
soong --help

# Should show:
# Usage: soong [OPTIONS] COMMAND [ARGS]...
```

```bash
# Check Python imports
python -c "from soong import cli, models, config; print('OK')"

# Should print: OK
```

### 5. Configure for Testing (Optional)

If you want to test against the real Lambda API:

```bash
soong configure
```

Enter:

- **Lambda API key**: Get from https://cloud.lambdalabs.com/api-keys
- **Status daemon token**: Any secure random string (or generate one)
- **Default region**: `us-west-1` or your preferred region
- **Filesystem name**: `coding-stack` (must exist in Lambda)
- **Default model**: `deepseek-r1-70b`
- **Default GPU**: `gpu_1x_a100_sxm4_80gb`
- **Lease hours**: `4`
- **SSH key path**: `~/.ssh/id_rsa`

For development, you can use dummy values since tests use mocks:

```yaml
# ~/.config/gpu-dashboard/config.yaml
lambda:
  api_key: "test_key_12345"
  default_region: "us-west-1"
  filesystem_name: "test-fs"

status_daemon:
  token: "test_token_67890"
  port: 8080

defaults:
  model: "deepseek-r1-70b"
  gpu: "gpu_1x_a100_sxm4_80gb"
  lease_hours: 4

ssh:
  key_path: "~/.ssh/id_rsa"
```

## Development Tools

### Code Editor Setup

#### VS Code

Install recommended extensions:

- **Python** (ms-python.python)
- **Pylance** (ms-python.vscode-pylance)
- **Python Test Explorer** (littlefoxteam.vscode-python-test-adapter)

Workspace settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": [
    "tests"
  ],
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.rulers": [88]
}
```

#### PyCharm

1. Open `cli/` directory as project
2. Configure interpreter: Settings → Project → Python Interpreter → Add → Existing environment
3. Select `cli/venv/bin/python`
4. Enable pytest: Settings → Tools → Python Integrated Tools → Testing → pytest

### Linting and Formatting (Optional)

Install development tools:

```bash
pip install black flake8 mypy
```

**Format code:**

```bash
black src/soong tests
```

**Check style:**

```bash
flake8 src/soong tests --max-line-length=88 --extend-ignore=E203
```

**Type checking:**

```bash
mypy src/soong --ignore-missing-imports
```

## Running the CLI in Development Mode

Since you installed with `-e`, any changes to the source code are immediately reflected:

```bash
# Edit src/soong/cli.py
# Then immediately test:
soong --help
```

### Testing Changes

**Method 1: Direct invocation**

```bash
soong status
soong start --help
```

**Method 2: Python module**

```bash
python -m soong.cli status
```

**Method 3: Testing individual functions**

```python
# In Python REPL
from soong.models import estimate_vram, Quantization

result = estimate_vram(70, Quantization.INT4, 8192)
print(result)
```

## Project Structure

Understanding the codebase:

```
cli/
├── src/soong/          # Main package
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # CLI commands (Typer app)
│   ├── config.py             # Configuration management
│   ├── instance.py           # Instance lifecycle
│   ├── lambda_api.py         # API client
│   ├── ssh.py                # SSH tunnels
│   ├── models.py             # Model definitions
│   └── history.py            # Termination history
│
├── tests/                    # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── helpers/              # Test utilities
│   └── test_*.py             # Test modules
│
├── pyproject.toml            # Project metadata
└── README.md                 # Package documentation
```

### Key Files

**`cli.py`** - CLI interface

- Typer commands (`@app.command()`)
- User interaction (prompts, confirmations)
- Output formatting (tables, panels)

**`lambda_api.py`** - Lambda Labs API

- HTTP client with retry logic
- Dataclasses for API responses (`Instance`, `InstanceType`)
- Error handling (`LambdaAPIError`)

**`models.py`** - Model registry

- Model configurations (`ModelConfig`)
- VRAM estimation
- GPU recommendations
- Known GPUs and models

**`config.py`** - Configuration

- YAML config loading/saving
- Validation for custom models
- Secure file permissions

**`instance.py`** - Instance management

- Waiting for instances to become ready
- Status polling
- Active instance detection

**`ssh.py`** - SSH tunnels

- Background SSH tunnel creation
- Port forwarding
- PID tracking for cleanup

## Common Development Tasks

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=soong --cov-report=html

# Specific test file
pytest tests/test_models.py

# Specific test
pytest tests/test_models.py::test_estimate_vram_llama_70b_int4

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Adding a New Command

1. Add command function in `cli.py`:

```python
@app.command()
def my_command(
    arg: str = typer.Argument(..., help="Required argument"),
    option: bool = typer.Option(False, help="Optional flag"),
):
    """Brief description of the command."""
    config = get_config()
    # Implementation
    console.print("[green]Success![/green]")
```

2. Add tests in `tests/test_cli_commands.py`:

```python
def test_my_command_success(cli_runner, sample_config, mocker):
    """Test my_command with valid input."""
    mocker.patch("soong.cli.get_config", return_value=sample_config)
    result = cli_runner.invoke(app, ["my-command", "test-arg"])
    assert result.exit_code == 0
    assert "Success!" in result.output
```

3. Update documentation in `docs/`

### Debugging Tests

**Run test with debugger:**

```bash
pytest tests/test_models.py::test_estimate_vram_llama_70b_int4 --pdb
```

**Add breakpoint in code:**

```python
def estimate_vram(params_billions, quantization):
    import pdb; pdb.set_trace()  # Debugger will stop here
    base = params_billions * quantization.bytes_per_param
    ...
```

**See test output:**

```bash
# Show print statements and logging
pytest -s --log-cli-level=DEBUG
```

### Working with Mocks

Tests use `pytest-mock` and `responses` for mocking:

```python
def test_api_call(mock_http, lambda_api_base_url):
    """Test API call with mocked HTTP."""
    # Mock HTTP response
    mock_http.add(
        responses.GET,
        f"{lambda_api_base_url}/instances",
        json={"data": []},
        status=200,
    )

    # Call code that makes request
    api = LambdaAPI("test_key")
    instances = api.list_instances()

    # Verify
    assert len(instances) == 0
    assert len(mock_http.calls) == 1
```

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'soong'`

**Solution:**

```bash
# Make sure you're in the venv
source venv/bin/activate

# Reinstall in editable mode
pip install -e ".[test]"
```

### Test Failures

**Problem:** Tests fail with import errors

**Solution:**

```bash
# Install test dependencies
pip install -e ".[test]"

# Or explicitly
pip install pytest pytest-cov pytest-mock responses
```

### Virtual Environment Issues

**Problem:** Can't activate venv

**Solution:**

```bash
# Delete and recreate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e ".[test]"
```

### Config File Permission Errors

**Problem:** `PermissionError` when running tests

**Solution:**

```bash
# Fix permissions on config dir
chmod 755 ~/.config/gpu-dashboard
chmod 600 ~/.config/gpu-dashboard/config.yaml
```

## Next Steps

- Read [Testing Guide](testing.md) to learn about writing tests
- Check [Contributing Guide](index.md) for coding standards
- Explore the codebase and experiment with changes!

## Getting Help

If you encounter issues:

1. Check [GitHub Issues](https://github.com/axiomantic/soong/issues)
2. Search [Discussions](https://github.com/axiomantic/soong/discussions)
3. Ask in project chat/Slack (if available)
4. Create a new issue with:
   - Python version (`python --version`)
   - OS and version
   - Steps to reproduce
   - Error messages
