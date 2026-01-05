"""Tests for ConfigManager Cloudflare save/load."""

import tempfile
import yaml
from pathlib import Path
import pytest
from soong.config import (
    CloudflareConfig,
    Config,
    ConfigManager,
    LambdaConfig,
    StatusDaemonConfig,
)


@pytest.fixture
def temp_config_dir(monkeypatch):
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".config" / "gpu-dashboard"
        config_dir.mkdir(parents=True)

        # Mock the config directory
        def mock_init(self):
            self.config_dir = config_dir
            self.config_file = self.config_dir / "config.yaml"

        monkeypatch.setattr(ConfigManager, "__init__", mock_init)
        yield config_dir


def test_save_includes_cloudflare_section(temp_config_dir):
    """Test that ConfigManager.save() writes cloudflare section."""
    manager = ConfigManager()

    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        cloudflare=CloudflareConfig(
            api_token="cf-token-123",
            account_id="account-456",
        ),
    )

    manager.save(config)

    # Verify file was written
    assert manager.config_file.exists()

    # Load YAML and check cloudflare section
    with open(manager.config_file) as f:
        data = yaml.safe_load(f)

    assert "cloudflare" in data
    assert data["cloudflare"]["api_token"] == "cf-token-123"
    assert data["cloudflare"]["account_id"] == "account-456"
    assert data["cloudflare"]["worker_name"] == "gpu-watchdog"


def test_save_cloudflare_with_defaults(temp_config_dir):
    """Test saving cloudflare with default values."""
    manager = ConfigManager()

    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
    )

    manager.save(config)

    with open(manager.config_file) as f:
        data = yaml.safe_load(f)

    assert "cloudflare" in data
    assert data["cloudflare"]["api_token"] == ""
    assert data["cloudflare"]["account_id"] == ""
    assert data["cloudflare"]["kv_namespace_id"] == ""
    assert data["cloudflare"]["worker_url"] == ""
    assert data["cloudflare"]["worker_name"] == "gpu-watchdog"


def test_load_includes_cloudflare_section(temp_config_dir):
    """Test that ConfigManager.load() parses cloudflare section."""
    manager = ConfigManager()

    # Write test config file
    test_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
        "cloudflare": {
            "api_token": "cf-token-xyz",
            "account_id": "account-abc",
            "kv_namespace_id": "kv-123",
            "worker_url": "https://worker.example.com",
            "worker_name": "custom-watchdog",
        },
    }

    with open(manager.config_file, "w") as f:
        yaml.dump(test_data, f)

    # Load config
    config = manager.load()

    assert config is not None
    assert config.cloudflare.api_token == "cf-token-xyz"
    assert config.cloudflare.account_id == "account-abc"
    assert config.cloudflare.kv_namespace_id == "kv-123"
    assert config.cloudflare.worker_url == "https://worker.example.com"
    assert config.cloudflare.worker_name == "custom-watchdog"


def test_load_cloudflare_missing_uses_defaults(temp_config_dir):
    """Test that missing cloudflare section results in default CloudflareConfig."""
    manager = ConfigManager()

    # Write config without cloudflare section
    test_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
    }

    with open(manager.config_file, "w") as f:
        yaml.dump(test_data, f)

    config = manager.load()

    assert config is not None
    assert config.cloudflare.api_token == ""
    assert config.cloudflare.account_id == ""
    assert config.cloudflare.worker_name == "gpu-watchdog"


def test_load_cloudflare_partial_uses_defaults(temp_config_dir):
    """Test partial cloudflare config uses defaults for missing fields."""
    manager = ConfigManager()

    test_data = {
        "lambda": {"api_key": "test-key"},
        "status_daemon": {"token": "test-token"},
        "cloudflare": {
            "api_token": "partial-token",
        },
    }

    with open(manager.config_file, "w") as f:
        yaml.dump(test_data, f)

    config = manager.load()

    assert config is not None
    assert config.cloudflare.api_token == "partial-token"
    assert config.cloudflare.account_id == ""
    assert config.cloudflare.worker_name == "gpu-watchdog"
