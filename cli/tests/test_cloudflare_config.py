"""Tests for Cloudflare configuration."""

import pytest
from soong.config import CloudflareConfig, Config, LambdaConfig, StatusDaemonConfig


def test_cloudflare_config_dataclass_exists():
    """Test CloudflareConfig dataclass can be instantiated."""
    cf_config = CloudflareConfig(
        api_token="test_token_123",
        account_id="a1b2c3d4e5f6" * 4,  # 32 chars
    )
    assert cf_config.api_token == "test_token_123"
    assert cf_config.account_id == "a1b2c3d4e5f6" * 4


def test_cloudflare_config_defaults():
    """Test CloudflareConfig has correct defaults."""
    cf_config = CloudflareConfig()
    assert cf_config.api_token == ""
    assert cf_config.account_id == ""
    assert cf_config.kv_namespace_id == ""
    assert cf_config.worker_url == ""
    assert cf_config.worker_name == "gpu-watchdog"


def test_config_includes_cloudflare():
    """Test Config dataclass has cloudflare field."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
    )
    assert hasattr(config, "cloudflare")
    assert isinstance(config.cloudflare, CloudflareConfig)


def test_config_cloudflare_defaults_in_post_init():
    """Test Config.__post_init__ creates CloudflareConfig if None."""
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        cloudflare=None,
    )
    assert config.cloudflare is not None
    assert isinstance(config.cloudflare, CloudflareConfig)


def test_config_cloudflare_can_be_provided():
    """Test Config accepts explicit CloudflareConfig."""
    cf_config = CloudflareConfig(
        api_token="token123",
        account_id="account456",
    )
    config = Config(
        lambda_config=LambdaConfig(api_key="test-key"),
        status_daemon=StatusDaemonConfig(token="test-token"),
        cloudflare=cf_config,
    )
    assert config.cloudflare == cf_config
