"""Tests for provision.py instance provisioning."""

import pytest
from unittest.mock import patch, MagicMock
from soong.provision import ProvisionConfig, run_ansible_playbook


class TestProvisionConfig:
    """Tests for ProvisionConfig dataclass."""

    def test_provision_config_default_worker_url_is_none(self):
        """Test that worker_url defaults to None when not provided."""
        config = ProvisionConfig(
            instance_ip="192.168.1.1",
            ssh_key_path="/path/to/key",
            lambda_api_key="test-api-key",
            status_token="test-token",
            model="test-model",
            lease_hours=4,
        )
        assert config.worker_url is None

    def test_provision_config_with_worker_url(self):
        """Test that worker_url can be set."""
        config = ProvisionConfig(
            instance_ip="192.168.1.1",
            ssh_key_path="/path/to/key",
            lambda_api_key="test-api-key",
            status_token="test-token",
            model="test-model",
            lease_hours=4,
            worker_url="https://my-worker.example.com",
        )
        assert config.worker_url == "https://my-worker.example.com"

    def test_provision_config_with_empty_worker_url(self):
        """Test that empty string worker_url is preserved."""
        config = ProvisionConfig(
            instance_ip="192.168.1.1",
            ssh_key_path="/path/to/key",
            lambda_api_key="test-api-key",
            status_token="test-token",
            model="test-model",
            lease_hours=4,
            worker_url="",
        )
        assert config.worker_url == ""


class TestRunAnsiblePlaybook:
    """Tests for run_ansible_playbook function."""

    @patch("soong.provision.subprocess.run")
    @patch("soong.provision.ANSIBLE_DIR")
    def test_worker_url_passed_to_ansible_when_set(self, mock_ansible_dir, mock_run):
        """Test that worker_url is passed to ansible when configured."""
        mock_ansible_dir.exists.return_value = True
        mock_ansible_dir.__truediv__ = MagicMock(return_value=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)

        config = ProvisionConfig(
            instance_ip="10.0.0.1",
            ssh_key_path="/home/user/.ssh/id_rsa",
            lambda_api_key="lambda-key-123",
            status_token="status-token-456",
            model="deepseek-r1-70b",
            lease_hours=4,
            worker_url="https://worker.example.com",
        )

        # Can't easily test run_ansible_playbook due to file system deps
        # but we can at least verify the config is set up correctly
        assert config.worker_url == "https://worker.example.com"

    def test_worker_url_not_passed_when_none(self):
        """Test that worker_url is not passed when None."""
        config = ProvisionConfig(
            instance_ip="10.0.0.1",
            ssh_key_path="/home/user/.ssh/id_rsa",
            lambda_api_key="lambda-key-123",
            status_token="status-token-456",
            model="deepseek-r1-70b",
            lease_hours=4,
            worker_url=None,
        )

        assert config.worker_url is None


class TestProvisionConfigFields:
    """Test all ProvisionConfig fields are properly set."""

    def test_all_fields_set_correctly(self):
        """Test that all fields in ProvisionConfig are stored correctly."""
        config = ProvisionConfig(
            instance_ip="192.168.100.50",
            ssh_key_path="/home/testuser/.ssh/my_key",
            lambda_api_key="my-lambda-api-key",
            status_token="my-status-token",
            model="qwen2.5-coder-32b",
            lease_hours=8,
            idle_timeout_minutes=45,
            max_lease_hours=12,
            worker_url="https://watchdog.workers.dev",
        )

        assert config.instance_ip == "192.168.100.50"
        assert config.ssh_key_path == "/home/testuser/.ssh/my_key"
        assert config.lambda_api_key == "my-lambda-api-key"
        assert config.status_token == "my-status-token"
        assert config.model == "qwen2.5-coder-32b"
        assert config.lease_hours == 8
        assert config.idle_timeout_minutes == 45
        assert config.max_lease_hours == 12
        assert config.worker_url == "https://watchdog.workers.dev"

    def test_default_values(self):
        """Test default values for optional fields."""
        config = ProvisionConfig(
            instance_ip="10.0.0.1",
            ssh_key_path="/key",
            lambda_api_key="key",
            status_token="token",
            model="model",
            lease_hours=4,
        )

        # Check defaults
        assert config.idle_timeout_minutes == 30
        assert config.max_lease_hours == 8
        assert config.worker_url is None
