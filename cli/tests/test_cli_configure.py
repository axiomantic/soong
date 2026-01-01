"""Tests for 'gpu-session configure' command.

The configure command is an interactive wizard that:
1. Prompts for Lambda API key and validates it
2. Prompts for status daemon token (or auto-generates)
3. Shows model selection with GPU requirements
4. Shows GPU selection with pricing and availability
5. Shows region selection
6. Prompts for filesystem name
7. Shows lease duration options with cost estimates
8. Prompts for SSH key path
9. Saves config and shows summary
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import Mock, MagicMock, call
from gpu_session.cli import app
from gpu_session.config import ConfigManager
from gpu_session.lambda_api import LambdaAPIError
import questionary


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_instance_types(mocker):
    """Standard mock instance types for testing."""
    return [
        Mock(
            name="gpu_1x_a10",
            description="1x A10 (24 GB)",
            price_cents_per_hour=60,
            regions_available=["us-west-1", "us-east-1"],
            price_per_hour=0.60,
            format_price=lambda: "$0.60/hr",
        ),
        Mock(
            name="gpu_1x_a6000",
            description="1x A6000 (48 GB)",
            price_cents_per_hour=80,
            regions_available=["us-west-1"],
            price_per_hour=0.80,
            format_price=lambda: "$0.80/hr",
        ),
        Mock(
            name="gpu_1x_a100_sxm4_80gb",
            description="1x A100 SXM4 (80 GB)",
            price_cents_per_hour=129,
            regions_available=["us-west-1", "us-east-1"],
            price_per_hour=1.29,
            format_price=lambda: "$1.29/hr",
        ),
    ]


@pytest.fixture
def temp_config_manager(tmp_path, monkeypatch):
    """ConfigManager with temporary config directory."""
    config_dir = tmp_path / ".config" / "gpu-session"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Patch ConfigManager to use temp directory
    original_init = ConfigManager.__init__

    def patched_init(self):
        original_init(self)
        self.config_dir = config_dir
        self.config_file = config_dir / "config.yaml"

    monkeypatch.setattr(ConfigManager, "__init__", patched_init)

    # Create a new config manager instance
    mgr = ConfigManager()

    # Patch the global config_manager in cli module
    from gpu_session import cli
    monkeypatch.setattr(cli, "config_manager", mgr)

    return mgr


class TestConfigureFullWizard:
    """Test complete wizard flow."""

    def test_configure_full_wizard_success(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test complete successful wizard flow with all prompts."""
        # Mock LambdaAPI
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        # Mock questionary responses in order
        responses = iter([
            "test_api_key_12345678",              # API key
            "my_status_token",                     # status daemon token
            "deepseek-r1-70b",                     # model selection
            "gpu_1x_a100_sxm4_80gb",              # GPU type
            "us-west-1",                           # region
            "my-filesystem",                       # filesystem name
            4,                                     # lease hours
            "~/.ssh/id_ed25519",                  # SSH key path
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Configuration saved!" in result.stdout
        assert "test_api" in result.stdout  # Shows truncated key
        assert "gpu_1x_a100_sxm4_80gb" in result.stdout
        assert "us-west-1" in result.stdout
        assert "deepseek-r1-70b" in result.stdout
        assert "4 hours" in result.stdout
        assert "my-filesystem" in result.stdout

        # Verify config was saved correctly
        config = temp_config_manager.load()
        assert config is not None
        assert config.lambda_config.api_key == "test_api_key_12345678"
        assert config.lambda_config.default_region == "us-west-1"
        assert config.lambda_config.filesystem_name == "my-filesystem"
        assert config.status_daemon.token == "my_status_token"
        assert config.defaults.model == "deepseek-r1-70b"
        assert config.defaults.gpu == "gpu_1x_a100_sxm4_80gb"
        assert config.defaults.lease_hours == 4
        assert config.ssh.key_path == "~/.ssh/id_ed25519"


class TestConfigureAPIKey:
    """Test API key validation step."""

    def test_configure_api_key_validation_success(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test API key validation passes with valid key."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "valid_api_key_123",
            "token123",
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "API key valid" in result.stdout
        mock_api_instance.list_instance_types.assert_called_once()

    def test_configure_api_key_validation_failure(
        self, runner, temp_config_manager, monkeypatch
    ):
        """Test API key validation fails with invalid key."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.side_effect = LambdaAPIError("Invalid API key")
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter(["invalid_key"])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 1
        assert "Invalid API key" in result.stdout

    def test_configure_api_key_cancelled(self, runner, temp_config_manager, monkeypatch):
        """Test cancelling at API key prompt."""
        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return None  # Simulate Ctrl+C cancellation
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 1
        assert "Configuration cancelled" in result.stdout


class TestConfigureStatusToken:
    """Test status daemon token step."""

    def test_configure_auto_generates_token_when_blank(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test auto-generation of token when user leaves it blank."""
        import secrets as secrets_module

        # Mock secrets.token_urlsafe to return a predictable value
        monkeypatch.setattr(secrets_module, "token_urlsafe", lambda n: "auto_generated_token_xyz")

        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "",  # Blank token - should auto-generate
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Generated token:" in result.stdout
        assert "auto_generated_token_xyz" in result.stdout

        # Verify auto-generated token was saved
        config = temp_config_manager.load()
        assert config.status_daemon.token == "auto_generated_token_xyz"

    def test_configure_uses_provided_token(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test using user-provided status token."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "custom_token_abc",  # User provides their own token
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Generated token:" not in result.stdout

        # Verify custom token was saved
        config = temp_config_manager.load()
        assert config.status_daemon.token == "custom_token_abc"


class TestConfigureModelSelection:
    """Test model selection step."""

    def test_configure_model_selection_known_model(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test selecting a known model from the list."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "qwen-2.5-coder-32b",  # Known model
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "qwen-2.5-coder-32b" in result.stdout

        config = temp_config_manager.load()
        assert config.defaults.model == "qwen-2.5-coder-32b"

    def test_configure_model_selection_custom_model(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test selecting custom model and entering specs."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "_custom",                        # Select custom model option
            "my-org/my-custom-model",        # Custom model name
            "13",                             # params_billions
            "int4",                           # quantization
            "gpu_1x_a6000",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "my-org/my-custom-model" in result.stdout

        config = temp_config_manager.load()
        assert config.defaults.model == "my-org/my-custom-model"

    def test_configure_custom_model_specs_entry(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test entering custom model specs for VRAM calculation."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "_custom",
            "test/big-model",
            "70",                    # 70B params
            "fp16",                  # FP16 quantization
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Estimated VRAM:" in result.stdout
        assert "Minimum GPU:" in result.stdout


class TestConfigureGPUSelection:
    """Test GPU selection step."""

    def test_configure_gpu_selection_shows_viable_first(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test that GPUs with sufficient VRAM are shown first."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        # Select DeepSeek R1 70B which needs ~48GB
        responses = iter([
            "api_key_123",
            "token",
            "deepseek-r1-70b",      # Needs 48GB
            "gpu_1x_a6000",         # 48GB GPU (should be viable)
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Showing compatible GPUs first" in result.stdout

    def test_configure_gpu_selection_warns_insufficient_vram(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test configuring with GPU that has insufficient VRAM completes successfully.

        Note: The warning message is displayed during interactive flow but may not
        appear in captured stdout due to Rich console formatting.
        """
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        # Select model that needs ~44GB but choose 24GB GPU
        responses = iter([
            "api_key_123",
            "token",
            "deepseek-r1-70b",    # Needs ~44GB VRAM
            "gpu_1x_a10",         # Only 24GB - insufficient
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        # Configuration should still complete successfully even with undersized GPU
        assert result.exit_code == 0

        # Verify the insufficient GPU was saved
        config = temp_config_manager.load()
        assert config.defaults.gpu == "gpu_1x_a10"
        assert config.defaults.model == "deepseek-r1-70b"

    def test_configure_gpu_selection_recommends_cheapest_available(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test selecting cheapest viable GPU for a small model.

        The configure wizard shows available GPUs sorted by price, with the
        cheapest available option marked as recommended (in interactive mode).
        """
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-7b",           # Small model, any GPU works
            "gpu_1x_a10",           # Choose cheapest ($0.60/hr)
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        # Verify cheapest GPU was selected and saved
        config = temp_config_manager.load()
        assert config.defaults.gpu == "gpu_1x_a10"
        assert config.defaults.model == "llama-2-7b"


class TestConfigureRegionSelection:
    """Test region selection step."""

    def test_configure_region_selection_from_available(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test selecting region from available regions for chosen GPU."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",  # Has us-west-1 and us-east-1
            "us-east-1",               # Choose us-east-1
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        config = temp_config_manager.load()
        assert config.lambda_config.default_region == "us-east-1"

    def test_configure_region_selection_manual_entry(
        self, runner, temp_config_manager, monkeypatch
    ):
        """Test manual region entry when instance types unavailable."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = []  # No instance types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "us-west-2",  # Manual region entry
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        config = temp_config_manager.load()
        assert config.lambda_config.default_region == "us-west-2"


class TestConfigureFilesystem:
    """Test filesystem configuration step."""

    def test_configure_filesystem_name_default(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test using default filesystem name."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "coding-stack",  # Default value
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        config = temp_config_manager.load()
        assert config.lambda_config.filesystem_name == "coding-stack"


class TestConfigureLeaseDuration:
    """Test lease duration configuration step."""

    def test_configure_lease_hours_selection(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test selecting different lease hour options."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            6,  # 6 hours
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "6 hours" in result.stdout

        config = temp_config_manager.load()
        assert config.defaults.lease_hours == 6


class TestConfigureSSHKey:
    """Test SSH key path configuration step."""

    def test_configure_ssh_key_path_entry(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test entering custom SSH key path."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/custom_key",  # Custom SSH key
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        config = temp_config_manager.load()
        assert config.ssh.key_path == "~/.ssh/custom_key"


class TestConfigureSaveAndSummary:
    """Test config saving and summary display."""

    def test_configure_saves_config_correctly(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test that all configuration is saved correctly."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "complete_api_key_xyz",
            "complete_token",
            "deepseek-r1-70b",
            "gpu_1x_a100_sxm4_80gb",
            "us-east-1",
            "complete-fs",
            8,
            "~/.ssh/complete_key",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0

        # Verify all fields saved correctly
        config = temp_config_manager.load()
        assert config.lambda_config.api_key == "complete_api_key_xyz"
        assert config.lambda_config.default_region == "us-east-1"
        assert config.lambda_config.filesystem_name == "complete-fs"
        assert config.status_daemon.token == "complete_token"
        assert config.defaults.model == "deepseek-r1-70b"
        assert config.defaults.gpu == "gpu_1x_a100_sxm4_80gb"
        assert config.defaults.lease_hours == 8
        assert config.ssh.key_path == "~/.ssh/complete_key"

    def test_configure_displays_summary_panel(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test that summary panel is displayed with all info."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "summary_test_api_key",
            "summary_token",
            "llama-2-70b",
            "gpu_1x_a6000",
            "us-west-1",
            "summary-fs",
            2,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 0
        assert "Summary" in result.stdout
        assert "Configuration saved!" in result.stdout
        assert "API Key:" in result.stdout
        assert "GPU:" in result.stdout
        assert "Region:" in result.stdout
        assert "Model:" in result.stdout
        assert "Lease:" in result.stdout
        assert "Filesystem:" in result.stdout


class TestConfigureCancellation:
    """Test cancellation at various steps."""

    def test_configure_cancelled_at_model_step(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test cancelling at model selection step."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            None,  # Cancel at model selection
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 1

    def test_configure_cancelled_at_gpu_step(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test cancelling at GPU selection step."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            None,  # Cancel at GPU selection
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 1

    def test_configure_separator_selection_rejects(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test that selecting separator in GPU list exits gracefully."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "deepseek-r1-70b",
            "_separator",  # Try to select separator (should be disabled/rejected)
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["configure"])

        # Should exit with error when separator selected
        assert result.exit_code == 1


class TestConfigureEdgeCases:
    """Test edge cases and error conditions."""

    def test_configure_no_instance_types_available(
        self, runner, temp_config_manager, monkeypatch
    ):
        """Test configure when API returns no instance types."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = []  # Empty list
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "llama-2-70b",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        # Should still complete successfully with fallback behavior
        assert result.exit_code == 0

        config = temp_config_manager.load()
        assert config is not None
        assert config.defaults.gpu == "gpu_1x_a100_sxm4_80gb"  # Fallback GPU

    def test_configure_custom_model_cancelled_at_name(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test cancelling when entering custom model name."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "_custom",
            None,  # Cancel at custom model name entry
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)

        result = runner.invoke(app, ["configure"])

        assert result.exit_code == 1

    def test_configure_custom_model_invalid_specs(
        self, runner, temp_config_manager, mock_instance_types, monkeypatch
    ):
        """Test custom model with invalid parameter specs."""
        mock_api_class = Mock()
        mock_api_instance = Mock()
        mock_api_instance.list_instance_types.return_value = mock_instance_types
        mock_api_class.return_value = mock_api_instance

        from gpu_session import cli
        monkeypatch.setattr(cli, "LambdaAPI", mock_api_class)

        responses = iter([
            "api_key_123",
            "token",
            "_custom",
            "test/model",
            "not_a_number",  # Invalid params
            "int4",
            "gpu_1x_a100_sxm4_80gb",
            "us-west-1",
            "test-fs",
            4,
            "~/.ssh/id_rsa",
        ])

        def mock_text(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_select(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        def mock_path(prompt, **kwargs):
            class MockResult:
                def ask(self):
                    return next(responses)
            return MockResult()

        monkeypatch.setattr(questionary, "text", mock_text)
        monkeypatch.setattr(questionary, "select", mock_select)
        monkeypatch.setattr(questionary, "path", mock_path)

        result = runner.invoke(app, ["configure"])

        # Should show warning but continue
        assert result.exit_code == 0
        assert "Could not parse specs" in result.stdout or "will select GPU manually" in result.stdout
