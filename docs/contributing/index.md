# Contributing Guide

Thank you for your interest in contributing to soong CLI! This guide will help you get started with development, testing, and submitting contributions.

## Contents

- [Development Setup](development-setup.md) - Set up your local development environment
- [Testing](testing.md) - Run tests and add new test coverage

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/my-ai.git
cd my-ai/cli

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with test dependencies
pip install -e ".[test]"

# Run tests
pytest

# Run the CLI in development mode
soong --help
```

## Project Structure

```
cli/
├── src/
│   └── soong/
│       ├── __init__.py
│       ├── cli.py              # CLI commands and interface
│       ├── config.py           # Configuration management
│       ├── instance.py         # Instance lifecycle management
│       ├── lambda_api.py       # Lambda Labs API client
│       ├── ssh.py              # SSH tunnel management
│       ├── models.py           # Model definitions and GPU mapping
│       └── history.py          # Termination history tracking
├── tests/
│   ├── conftest.py            # Shared test fixtures
│   ├── test_*.py              # Test modules
│   └── helpers/
│       └── assertions.py      # Custom test assertions
├── pyproject.toml             # Project metadata and dependencies
└── README.md                  # CLI documentation
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow the coding standards outlined below.

### 3. Write Tests

All new features and bug fixes should include tests. See [Testing](testing.md) for details.

### 4. Run Tests Locally

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=soong --cov-report=term-missing

# Run specific test file
pytest tests/test_models.py

# Run specific test
pytest tests/test_models.py::test_estimate_vram_llama_70b_int4
```

### 5. Submit a Pull Request

- Push your branch to GitHub
- Create a pull request with a clear description
- Ensure all CI checks pass
- Request review from maintainers

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Imports**: Grouped by standard library, third-party, local

### Type Hints

All public functions should have type hints:

```python
def launch_instance(
    region: str,
    instance_type: str,
    ssh_key_names: List[str],
    filesystem_names: Optional[List[str]] = None,
) -> str:
    """Launch a new GPU instance."""
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def estimate_vram(
    params_billions: float,
    quantization: Quantization = Quantization.FP16,
    context_length: int = 8192,
) -> dict:
    """
    Estimate VRAM requirements for any model.

    Args:
        params_billions: Parameter count in billions
        quantization: Quantization level
        context_length: Context window size

    Returns:
        Dict with VRAM estimates and recommended GPU

    Example:
        >>> estimate_vram(70, Quantization.INT4, 8192)
        {'base_vram_gb': 35.0, 'total_estimated_gb': 41.1, ...}
    """
    ...
```

### Error Handling

Use specific exception types and provide helpful error messages:

```python
# Good
if not instance:
    console.print("[red]Error: Instance not found[/red]")
    raise typer.Exit(1)

# Bad
if not instance:
    raise Exception("error")
```

### CLI Output

Use Rich console for all output:

```python
from rich.console import Console
console = Console()

# Success
console.print("[green]Instance launched successfully[/green]")

# Error
console.print("[red]Error: API key invalid[/red]")

# Warning
console.print("[yellow]Warning: Lease will expire in 10 minutes[/yellow]")

# Info
console.print("[cyan]Checking instance status...[/cyan]")
```

## Code Organization

### Adding New Commands

New CLI commands go in `cli.py`:

```python
@app.command()
def your_command(
    arg1: str = typer.Argument(..., help="Required argument"),
    option1: Optional[str] = typer.Option(None, help="Optional flag"),
):
    """Brief description of what this command does."""
    config = get_config()
    # Implementation
```

### Adding New Models

Add model definitions to `models.py`:

```python
_register_model(
    model_id="your-model",
    name="Your Model Name",
    hf_path="org/model-name",
    params_billions=13,
    quantization=Quantization.FP16,
    context_length=8192,
    description="Brief description",
    good_for=["Use case 1", "Use case 2"],
    not_good_for=["Anti-pattern 1"],
    notes="Additional information",
)
```

### Adding API Endpoints

Extend `LambdaAPI` class in `lambda_api.py`:

```python
def new_endpoint(self, param: str) -> ResultType:
    """
    Call new Lambda API endpoint.

    Args:
        param: Description

    Returns:
        Parsed response

    Raises:
        LambdaAPIError: On API failure
    """
    resp = self._request_with_retry(
        "GET",
        f"endpoint/{param}",
    )
    data = resp.json()
    return ResultType.from_api_response(data)
```

## Testing Philosophy

We aim for high test coverage while avoiding brittle tests. See [Testing](testing.md) for detailed guidelines.

### Key Principles

1. **Test behavior, not implementation**: Tests should verify what the code does, not how it does it
2. **Use realistic test data**: Avoid hardcoded values that would hide bugs
3. **Test error cases**: Verify error handling and edge cases
4. **Keep tests isolated**: Each test should be independent
5. **Make tests readable**: Use descriptive names and clear assertions

## Documentation

### Code Comments

Use comments sparingly for complex logic:

```python
# Calculate VRAM with 10% headroom for safety
min_gpu = total_vram * 1.1
```

Most code should be self-documenting through clear naming.

### User Documentation

User-facing documentation lives in `docs/`:

- Update `docs/` when adding features
- Include examples for new commands
- Document all CLI flags and options
- Add troubleshooting for common issues

## Common Tasks

### Adding a New GPU Type

1. Add to `KNOWN_GPUS` in `models.py`:

```python
KNOWN_GPUS = {
    "gpu_1x_new_gpu": {
        "vram_gb": 96,
        "description": "1x New GPU (96 GB)"
    },
    ...
}
```

2. Update tests in `test_models.py`
3. Update documentation in `docs/reference/gpu-types.md`

### Adding a New Configuration Option

1. Add to dataclass in `config.py`:

```python
@dataclass
class DefaultsConfig:
    model: str = "deepseek-r1-70b"
    gpu: str = "gpu_1x_a100_sxm4_80gb"
    lease_hours: int = 4
    new_option: str = "default_value"  # New option
```

2. Update `configure` command in `cli.py`
3. Add validation if needed
4. Update documentation

### Debugging Tips

**Enable verbose output:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Test API calls without launching:**

```python
# In cli.py
if dry_run:
    console.print(f"[dim]Would launch: {gpu} in {region}[/dim]")
    return
```

**Mock expensive operations in tests:**

```python
def test_launch(mocker):
    mock_api = mocker.Mock()
    mock_api.launch_instance.return_value = "inst_test123"
    # Test without actual API call
```

## Getting Help

- **Issues**: Check [GitHub Issues](https://github.com/yourusername/my-ai/issues)
- **Discussions**: Join [GitHub Discussions](https://github.com/yourusername/my-ai/discussions)
- **Documentation**: Read the [full documentation](../index.md)

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers and help them learn
- Focus on what is best for the project
- Show empathy towards other contributors

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (check LICENSE file).
