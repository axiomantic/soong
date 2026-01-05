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


@patch('soong.worker.subprocess.run')
def test_set_worker_secret_success(mock_run):
    """Test set_worker_secret passes secret via stdin."""
    from soong.worker import set_worker_secret

    # Mock successful secret setting
    mock_run.return_value = Mock(
        returncode=0,
        stdout='✓ Success',
        stderr='',
    )

    set_worker_secret("TEST_SECRET", "secret_value_123")

    # Verify wrangler was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args

    # Verify command
    cmd = call_args[0][0]
    assert cmd == ["npx", "wrangler", "secret", "put", "TEST_SECRET"]

    # Verify secret was passed via stdin
    assert call_args[1]['input'] == "secret_value_123"
    assert call_args[1]['text'] is True
    assert call_args[1]['capture_output'] is True


@patch('soong.worker.subprocess.run')
def test_set_worker_secret_failure(mock_run):
    """Test set_worker_secret raises RuntimeError on wrangler failure."""
    from soong.worker import set_worker_secret

    # Mock failed secret setting
    mock_run.return_value = Mock(
        returncode=1,
        stderr='Authentication failed',
    )

    with pytest.raises(RuntimeError, match="Failed to set secret TEST_SECRET"):
        set_worker_secret("TEST_SECRET", "secret_value")


def test_update_wrangler_toml(tmp_path):
    """Test update_wrangler_toml replaces placeholder correctly."""
    from soong.worker import update_wrangler_toml, WORKER_DIR
    from unittest.mock import patch

    # Create temporary wrangler.toml
    test_toml = tmp_path / "wrangler.toml"
    test_toml.write_text('''
name = "gpu-watchdog"
main = "src/index.ts"

[[kv_namespaces]]
binding = "KV"
id = "REPLACE_WITH_YOUR_KV_NAMESPACE_ID"
''')

    # Patch WORKER_DIR to use our temp directory
    with patch('soong.worker.WORKER_DIR', tmp_path):
        update_wrangler_toml("new_kv_namespace_abc123")

    # Verify placeholder was replaced
    updated_content = test_toml.read_text()
    assert 'id = "new_kv_namespace_abc123"' in updated_content
    assert 'REPLACE_WITH_YOUR_KV_NAMESPACE_ID' not in updated_content


@patch('soong.worker.subprocess.run')
@patch('soong.worker.requests.get')
@patch('soong.worker.update_wrangler_toml')
def test_deploy_worker_full_flow(mock_update_toml, mock_get, mock_run, tmp_path):
    """Test complete deployment flow with all steps."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key_full"),
        status_daemon=StatusDaemonConfig(token="status_token_full"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="existing_kv_456",  # Already exists
            worker_url="",
        ),
    )

    # Mock all subprocess calls
    def mock_subprocess(cmd, **kwargs):
        if 'node' in cmd and '--version' in cmd:
            return Mock(returncode=0, stdout='v20.0.0', stderr='')
        elif 'secret' in cmd and 'put' in cmd:
            return Mock(returncode=0, stdout='✓', stderr='')
        elif 'deploy' in cmd:
            return Mock(
                returncode=0,
                stdout='Published gpu-watchdog\n  https://gpu-watchdog.full-test.workers.dev',
                stderr='',
            )
        else:
            return Mock(returncode=0, stdout='', stderr='')

    mock_run.side_effect = mock_subprocess

    # Mock health check
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {"status": "healthy", "kv_available": True},
    )

    # Mock node_modules existence
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    with patch('soong.worker.WORKER_DIR', tmp_path):
        manager = ConfigManager()
        manager.config_dir = tmp_path
        manager.config_file = tmp_path / "config.yaml"
        manager.save(config)

        updated_config = deploy_worker(config, manager)

    # Verify configuration was updated
    assert updated_config.cloudflare.worker_url == "https://gpu-watchdog.full-test.workers.dev"
    assert updated_config.cloudflare.kv_namespace_id == "existing_kv_456"

    # Verify wrangler.toml was updated
    mock_update_toml.assert_called_once_with("existing_kv_456")

    # Verify secrets were set (2 calls: LAMBDA_API_KEY and STATUS_DAEMON_TOKEN)
    secret_calls = [call for call in mock_run.call_args_list if 'secret' in str(call)]
    assert len(secret_calls) == 2

    # Verify health check was performed
    mock_get.assert_called_once()


@patch('soong.worker.requests.get')
def test_worker_status_connection_error(mock_get):
    """Test worker_status handles connection errors gracefully."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig
    import requests

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            worker_url="https://gpu-watchdog.test.workers.dev",
        ),
    )

    # Mock connection error
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

    with pytest.raises(RuntimeError, match="Failed to fetch Worker status"):
        worker_status(config)


def test_worker_status_not_deployed():
    """Test worker_status raises error when Worker is not deployed."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            worker_url="",  # Not deployed
        ),
    )

    with pytest.raises(RuntimeError, match="Worker not deployed"):
        worker_status(config)


@patch('soong.worker.subprocess.run')
def test_destroy_worker_kv_deletion_failure(mock_run, tmp_path):
    """Test destroy_worker handles KV deletion failures gracefully."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="test_kv_789",
            worker_url="https://gpu-watchdog.test.workers.dev",
        ),
    )

    # Mock failed KV deletion (but don't raise exception)
    mock_run.return_value = Mock(
        returncode=1,
        stderr="KV namespace not found or already deleted",
    )

    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"
    manager.save(config)

    # Run with force to skip confirmation
    updated_config = destroy_worker(config, manager, force=True)

    # Verify config was still cleared despite deletion failure
    assert updated_config.cloudflare.kv_namespace_id == ""
    assert updated_config.cloudflare.worker_url == ""


def test_destroy_worker_no_deployment(tmp_path):
    """Test destroy_worker with no existing deployment."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="",
            worker_url="",
        ),
    )

    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"

    # Should return unchanged config without error
    result = destroy_worker(config, manager, force=True)

    assert result.cloudflare.kv_namespace_id == ""
    assert result.cloudflare.worker_url == ""


@patch('soong.worker.subprocess.run')
def test_deploy_worker_node_not_found(mock_run, tmp_path):
    """Test deploy_worker raises error when Node.js is not installed."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(),
    )

    # Mock Node.js not found
    mock_run.side_effect = FileNotFoundError("node: command not found")

    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.config_file = tmp_path / "config.yaml"

    with pytest.raises(RuntimeError, match="Node.js not found"):
        deploy_worker(config, manager)


@patch('soong.worker.subprocess.run')
def test_deploy_worker_kv_creation_failure(mock_run, tmp_path):
    """Test deploy_worker handles KV namespace creation failure."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="",  # Not set - will trigger creation
        ),
    )

    # Mock subprocess calls
    def mock_subprocess(cmd, **kwargs):
        if 'node' in cmd and '--version' in cmd:
            return Mock(returncode=0, stdout='v20.0.0', stderr='')
        elif 'kv:namespace' in cmd and 'create' in cmd:
            # KV creation fails
            return Mock(
                returncode=1,
                stderr='Authentication failed',
            )
        else:
            return Mock(returncode=0, stdout='', stderr='')

    mock_run.side_effect = mock_subprocess

    # Mock node_modules existence
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    with patch('soong.worker.WORKER_DIR', tmp_path):
        manager = ConfigManager()
        manager.config_dir = tmp_path
        manager.config_file = tmp_path / "config.yaml"
        manager.save(config)

        with pytest.raises(RuntimeError, match="KV namespace creation failed"):
            deploy_worker(config, manager)


@patch('soong.worker.subprocess.run')
@patch('soong.worker.requests.get')
@patch('soong.worker.update_wrangler_toml')
def test_deploy_worker_deployment_failure(mock_update_toml, mock_get, mock_run, tmp_path):
    """Test deploy_worker handles Worker deployment failure."""
    from soong.config import Config, LambdaConfig, StatusDaemonConfig, CloudflareConfig, ConfigManager

    config = Config(
        lambda_config=LambdaConfig(api_key="lambda_key"),
        status_daemon=StatusDaemonConfig(token="status_token"),
        cloudflare=CloudflareConfig(
            kv_namespace_id="existing_kv_999",
        ),
    )

    # Mock subprocess calls
    def mock_subprocess(cmd, **kwargs):
        if 'node' in cmd and '--version' in cmd:
            return Mock(returncode=0, stdout='v20.0.0', stderr='')
        elif 'secret' in cmd and 'put' in cmd:
            return Mock(returncode=0, stdout='✓', stderr='')
        elif 'deploy' in cmd:
            # Deployment fails
            return Mock(
                returncode=1,
                stderr='Deployment error: invalid configuration',
            )
        else:
            return Mock(returncode=0, stdout='', stderr='')

    mock_run.side_effect = mock_subprocess

    # Mock node_modules existence
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    with patch('soong.worker.WORKER_DIR', tmp_path):
        manager = ConfigManager()
        manager.config_dir = tmp_path
        manager.config_file = tmp_path / "config.yaml"
        manager.save(config)

        with pytest.raises(RuntimeError, match="Worker deployment failed"):
            deploy_worker(config, manager)
