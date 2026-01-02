# Contributing to Soong

Thank you for your interest in contributing to Soong! This document provides guidelines and information for contributors.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment:

```bash
cd cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

## Development Workflow

### Running Tests

```bash
cd cli
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=soong --cov-report=term-missing
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and under 50 lines when possible

### Commit Messages

Use clear, descriptive commit messages:

- `feat: add new command for X`
- `fix: resolve issue with Y`
- `docs: update README with Z`
- `test: add tests for W`
- `refactor: simplify V`

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with appropriate tests
3. Ensure all tests pass locally
4. Update documentation if needed
5. Submit a pull request with a clear description

### PR Checklist

- [ ] Tests pass (`pytest tests/`)
- [ ] Code follows project style
- [ ] Documentation updated (if applicable)
- [ ] Commit messages are clear

## Reporting Issues

When reporting issues, please include:

- Soong version (`soong --version`)
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant error messages or logs

## Feature Requests

Feature requests are welcome! Please:

- Check existing issues first
- Describe the use case
- Explain why existing features don't meet the need

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue with the "question" label or start a discussion.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
