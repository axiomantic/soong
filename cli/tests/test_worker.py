"""Tests for worker.py Worker management commands."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from soong.worker import (
    parse_kv_namespace_id,
    parse_worker_url,
    deploy_worker,
    worker_status,
    worker_logs,
    destroy_worker,
)


def test_parse_kv_namespace_id_pattern_1():
    """Test parsing KV namespace ID from wrangler output (pattern 1)."""
    output = '''
🌀 Creating namespace with title "gpu-watchdog-KV"
✨ Success!
Add the following to your configuration file in your kv_namespaces array:
{ binding = "KV", id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" }
'''
    namespace_id = parse_kv_namespace_id(output)
    assert namespace_id == "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"


def test_parse_kv_namespace_id_pattern_2():
    """Test parsing KV namespace ID from alternate format."""
    output = '''
Creating KV namespace...
id: 1234567890abcdef1234567890abcdef
binding: KV
'''
    namespace_id = parse_kv_namespace_id(output)
    assert namespace_id == "1234567890abcdef1234567890abcdef"


def test_parse_kv_namespace_id_fails_on_invalid():
    """Test parse_kv_namespace_id raises ValueError on invalid output."""
    with pytest.raises(ValueError, match="Failed to parse KV namespace ID"):
        parse_kv_namespace_id("No ID here")


def test_parse_worker_url():
    """Test parsing Worker URL from wrangler deploy output."""
    output = '''
Total Upload: 25.34 KiB / gzip: 7.89 KiB
Uploaded gpu-watchdog (2.35 sec)
Published gpu-watchdog (0.24 sec)
  https://gpu-watchdog.elijah.workers.dev
Current Deployment ID: 12345678-90ab-cdef-1234-567890abcdef
'''
    url = parse_worker_url(output)
    assert url == "https://gpu-watchdog.elijah.workers.dev"


def test_parse_worker_url_fails_on_invalid():
    """Test parse_worker_url raises ValueError on invalid output."""
    with pytest.raises(ValueError, match="Failed to parse Worker URL"):
        parse_worker_url("No URL here")


@patch('soong.worker.subprocess.run')
@patch('soong.worker.requests.get')
def test_deploy_worker_creates_kv_namespace(mock_get, mock_run, tmp_path):
    """Test deploy_worker creates KV namespace if not configured."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    # Setup config without KV namespace
    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            api_token="cf_token",
            account_id="a1b2c3d4" * 8,
            kv_namespace_id="",  # Not set
            worker_url="",
        ),
    )

    # Mock subprocess calls
    def mock_subprocess(cmd, **kwargs):
        if 'kv:namespace' in cmd and 'create' in cmd:
            # KV namespace create
            return Mock(
                returncode=0,
                stdout='{ binding = "KV", id = "new_kv_namespace_123" }',
                stderr='',
            )
        elif 'deploy' in cmd:
            # Worker deploy
            return Mock(
                returncode=0,
                stdout='Published gpu-watchdog\n  https://gpu-watchdog.test.workers.dev',
                stderr='',
            )
        elif 'secret' in cmd and 'put' in cmd:
            # Secret put
            return Mock(returncode=0, stdout='', stderr='')
        else:
            return Mock(returncode=0, stdout='', stderr='')

    mock_run.side_effect = mock_subprocess

    # Mock health check
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {"status": "healthy"},
    )

    # Create mock config manager
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(config)

    # Run deploy_worker
    updated_config = deploy_worker(config, manager)

    # Verify KV namespace was created and saved
    assert updated_config.cloudflare.kv_namespace_id == "new_kv_namespace_123"
    assert updated_config.cloudflare.worker_url == "https://gpu-watchdog.test.workers.dev"

    # Verify wrangler commands were called
    assert mock_run.call_count >= 3  # kv create, secrets x2, deploy


@patch('soong.worker.requests.get')
def test_worker_status_healthy(mock_get):
    """Test worker_status with healthy Worker."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            worker_url="https://gpu-watchdog.test.workers.dev",
        ),
    )

    # Mock health endpoint
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "status": "healthy",
            "version": "1.0.0",
            "kv_available": True,
        }
    )

    result = worker_status(config)

    assert result["status"] == "healthy"
    assert result["version"] == "1.0.0"
    assert result["kv_available"] is True
    mock_get.assert_called_once()


@patch('soong.worker.requests.get')
def test_worker_status_unhealthy(mock_get):
    """Test worker_status with unhealthy Worker."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            worker_url="https://gpu-watchdog.test.workers.dev",
        ),
    )

    # Mock failed request
    mock_get.side_effect = Exception("Connection failed")

    with pytest.raises(RuntimeError, match="Failed to fetch Worker status"):
        worker_status(config)


@patch('soong.worker.subprocess.run')
def test_worker_logs_success(mock_run):
    """Test worker_logs streams logs successfully."""
    # Mock wrangler tail command
    mock_run.return_value = Mock(returncode=0)

    worker_logs()

    # Verify wrangler tail was called
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "wrangler" in cmd
    assert "tail" in cmd


@patch('soong.worker.subprocess.run')
def test_worker_logs_failure(mock_run):
    """Test worker_logs handles failure."""
    # Mock failed wrangler tail
    mock_run.return_value = Mock(
        returncode=1,
        stderr="Authentication failed"
    )

    with pytest.raises(RuntimeError, match="Failed to stream Worker logs"):
        worker_logs()


@patch('soong.worker.subprocess.run')
@patch('soong.worker.questionary.confirm')
def test_destroy_worker_with_confirmation(mock_confirm, mock_run, tmp_path):
    """Test destroy_worker with user confirmation."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="test_kv_123",
            worker_url="https://gpu-watchdog.test.workers.dev",
        ),
    )

    # Mock confirmation
    mock_confirm.return_value.ask.return_value = True

    # Mock subprocess
    mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

    # Create mock config manager
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(config)

    # Run destroy_worker
    updated_config = destroy_worker(config, manager, force=False)

    # Verify KV namespace was deleted
    assert mock_run.call_count >= 1
    cmd = mock_run.call_args[0][0]
    assert "kv:namespace" in cmd
    assert "delete" in cmd

    # Verify config was cleared
    assert updated_config.cloudflare.kv_namespace_id == ""
    assert updated_config.cloudflare.worker_url == ""


@patch('soong.worker.questionary.confirm')
def test_destroy_worker_cancelled(mock_confirm, tmp_path):
    """Test destroy_worker when user cancels."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="test_kv_123",
        ),
    )

    # Mock cancellation
    mock_confirm.return_value.ask.return_value = False

    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"

    # Run destroy_worker - should return unchanged config
    result = destroy_worker(config, manager, force=False)

    # Verify nothing changed
    assert result.cloudflare.kv_namespace_id == "test_kv_123"


@patch('soong.worker.subprocess.run')
def test_destroy_worker_with_force(mock_run, tmp_path):
    """Test destroy_worker with force flag skips confirmation."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="test_kv_123",
        ),
    )

    # Mock subprocess
    mock_run.return_value = Mock(returncode=0, stdout='', stderr='')

    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(config)

    # Run with force
    updated_config = destroy_worker(config, manager, force=True)

    # Verify deletion happened without confirmation
    assert updated_config.cloudflare.kv_namespace_id == ""
