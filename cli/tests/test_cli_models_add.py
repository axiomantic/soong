"""Tests for 'gpu-session models add' command.

Following TDD methodology:
1. Write failing tests first (RED)
2. Verify they fail for the right reason
3. Implement minimal code to pass (GREEN)
4. Refactor while keeping tests green
"""

import pytest
from typer.testing import CliRunner
from gpu_session.cli import app
from gpu_session.config import ConfigManager


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_manager_with_config(tmp_path, monkeypatch, sample_config):
    """ConfigManager with a temporary config file."""
    # Override config path to use tmp_path
    config_dir = tmp_path / ".config" / "gpu-session"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Patch ConfigManager to use temp directory
    original_init = ConfigManager.__init__

    def patched_init(self):
        original_init(self)
        self.config_dir = config_dir
        self.config_file = config_dir / "config.yaml"

    monkeypatch.setattr(ConfigManager, "__init__", patched_init)

    # Create a new config manager instance with the patched __init__
    mgr = ConfigManager()
    mgr.save(sample_config)

    # Patch the global config_manager in cli module
    from gpu_session import cli
    monkeypatch.setattr(cli, "config_manager", mgr)

    return mgr


class TestModelsAddInteractive:
    """Test interactive mode (using questionary prompts)."""

    def test_models_add_interactive_success(self, runner, config_manager_with_config, monkeypatch):
        """Test adding a model interactively with valid inputs."""
        # Mock questionary to provide answers
        responses = iter([
            "my-custom-model",                    # name/id
            "org/my-custom-model",                # hf_path
            "13",                                  # params_billions
            "int4",                                # quantization (from select)
            "8192",                                # context_length
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, choices, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        import questionary
        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["models", "add"])

        assert result.exit_code == 0
        assert "Model 'my-custom-model' added successfully" in result.stdout

        # Verify model was saved to config with complete validation
        config = config_manager_with_config.load()
        assert "my-custom-model" in config.custom_models

        # Verify complete model configuration (model is a dict)
        model = config.custom_models["my-custom-model"]
        assert isinstance(model, dict), "Model should be a dictionary"
        assert model["hf_path"] == "org/my-custom-model"
        assert model["params_billions"] == 13.0
        assert model["quantization"] == "int4"
        assert model["context_length"] == 8192

        # Verify HF path has valid format
        parts = model["hf_path"].split("/")
        assert len(parts) == 2, f"HF path should have org/model format, got: {model['hf_path']}"
        assert parts[0] == "org"
        assert parts[1] == "my-custom-model"

        # Verify all required keys present
        required_keys = ["hf_path", "params_billions", "quantization", "context_length"]
        for key in required_keys:
            assert key in model, f"Missing required key: {key}"

    def test_models_add_interactive_invalid_quantization(self, runner, config_manager_with_config, monkeypatch):
        """Test interactive mode rejects invalid quantization."""
        responses = iter([
            "test-model",
            "org/test",
            "7",
            "invalid_quant",  # Invalid quantization
            "4096",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, choices, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        import questionary
        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["models", "add"])

        assert result.exit_code == 1
        assert "Invalid quantization 'invalid_quant'" in result.stdout
        assert "Must be one of:" in result.stdout
        assert "fp32" in result.stdout and "fp16" in result.stdout


class TestModelsAddFlags:
    """Test non-interactive mode (using command flags)."""

    def test_models_add_with_all_flags(self, runner, config_manager_with_config):
        """Test adding model with all flags provided."""
        result = runner.invoke(app, [
            "models", "add",
            "--name", "flag-model",
            "--hf-path", "test-org/flag-model",
            "--params", "32",
            "--quantization", "fp16",
            "--context", "16384",
        ])

        assert result.exit_code == 0
        assert "Model 'flag-model' added successfully" in result.stdout

        # Verify saved
        config = config_manager_with_config.load()
        assert "flag-model" in config.custom_models
        assert config.custom_models["flag-model"]["params_billions"] == 32.0
        assert config.custom_models["flag-model"]["quantization"] == "fp16"
        assert config.custom_models["flag-model"]["context_length"] == 16384

    def test_models_add_flags_invalid_quantization(self, runner, config_manager_with_config):
        """Test flag mode rejects invalid quantization."""
        result = runner.invoke(app, [
            "models", "add",
            "--name", "test",
            "--hf-path", "org/test",
            "--params", "7",
            "--quantization", "invalid",
            "--context", "4096",
        ])

        assert result.exit_code == 1
        assert "Error: Invalid quantization 'invalid'" in result.stdout
        assert "Must be one of:" in result.stdout
        assert "fp32" in result.stdout and "fp16" in result.stdout

    def test_models_add_flags_missing_required(self, runner, config_manager_with_config):
        """Test flags mode requires all fields when any flag is provided."""
        # Missing --hf-path
        result = runner.invoke(app, [
            "models", "add",
            "--name", "incomplete",
            "--params", "7",
        ])

        assert result.exit_code == 2  # Typer exits with 2 for missing required options
        assert "Missing option" in result.stdout or "required" in result.stdout.lower()

    def test_models_add_flags_negative_params(self, runner, config_manager_with_config):
        """Test validation rejects negative params."""
        result = runner.invoke(app, [
            "models", "add",
            "--name", "bad-model",
            "--hf-path", "org/bad",
            "--params", "-5",
            "--quantization", "int4",
            "--context", "4096",
        ])

        assert result.exit_code == 1
        assert "params_billions must be a positive number" in result.stdout

    def test_models_add_flags_invalid_context(self, runner, config_manager_with_config):
        """Test validation rejects invalid context length."""
        result = runner.invoke(app, [
            "models", "add",
            "--name", "bad-context",
            "--hf-path", "org/bad",
            "--params", "7",
            "--quantization", "int4",
            "--context", "256",  # Too small, min is 512
        ])

        assert result.exit_code == 1
        assert "context_length must be an integer >= 512" in result.stdout


class TestModelsAddEdgeCases:
    """Test edge cases and error conditions."""

    def test_models_add_duplicate_name(self, runner, config_manager_with_config):
        """Test that adding a duplicate model name overwrites (or warns)."""
        # Add first model
        result1 = runner.invoke(app, [
            "models", "add",
            "--name", "duplicate",
            "--hf-path", "org/v1",
            "--params", "7",
            "--quantization", "int4",
            "--context", "4096",
        ])
        assert result1.exit_code == 0

        # Try to add again with same name
        result2 = runner.invoke(app, [
            "models", "add",
            "--name", "duplicate",
            "--hf-path", "org/v2",
            "--params", "13",
            "--quantization", "fp16",
            "--context", "8192",
        ])

        # Should either succeed with overwrite or show warning
        assert result2.exit_code == 0
        # The newer version should be in config
        config = config_manager_with_config.load()
        assert config.custom_models["duplicate"]["hf_path"] == "org/v2"

    def test_models_add_no_config_file(self, runner, tmp_path, monkeypatch):
        """Test that command fails gracefully if no config exists."""
        # Setup empty config directory
        config_dir = tmp_path / ".config" / "gpu-session"
        config_dir.mkdir(parents=True)

        original_init = ConfigManager.__init__

        def patched_init(self):
            original_init(self)
            self.config_dir = config_dir
            self.config_file = config_dir / "config.yaml"

        monkeypatch.setattr(ConfigManager, "__init__", patched_init)

        # Patch the global config_manager instance
        mgr = ConfigManager()
        from gpu_session import cli
        monkeypatch.setattr(cli, "config_manager", mgr)

        result = runner.invoke(app, [
            "models", "add",
            "--name", "test",
            "--hf-path", "org/test",
            "--params", "7",
            "--quantization", "int4",
            "--context", "4096",
        ])

        assert result.exit_code == 1
        assert "Not configured" in result.stdout or "Run 'gpu-session configure' first" in result.stdout
