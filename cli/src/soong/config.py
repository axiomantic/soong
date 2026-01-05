"""Configuration management for GPU session CLI."""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, asdict, field


def validate_custom_model(model_data: dict) -> None:
    """
    Validate custom model configuration.

    Args:
        model_data: Dictionary with model configuration

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    required = ["hf_path", "params_billions", "quantization", "context_length"]
    missing = [f for f in required if f not in model_data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    # Validate quantization
    valid_quants = ["fp32", "fp16", "bf16", "int8", "int4"]
    quant = model_data["quantization"].lower()
    if quant not in valid_quants:
        raise ValueError(
            f"Invalid quantization '{model_data['quantization']}'. "
            f"Must be one of: {', '.join(valid_quants)}"
        )

    # Validate params_billions
    params = model_data["params_billions"]
    if not isinstance(params, (int, float)) or params <= 0:
        raise ValueError("params_billions must be a positive number")

    # Validate context_length
    context = model_data["context_length"]
    if not isinstance(context, int) or context < 512:
        raise ValueError("context_length must be an integer >= 512")


@dataclass
class LambdaConfig:
    """Lambda Labs API configuration."""
    api_key: str
    default_region: str = "us-west-1"
    filesystem_name: str = "coding-stack"


@dataclass
class StatusDaemonConfig:
    """Status daemon configuration."""
    token: str
    port: int = 8080


@dataclass
class DefaultsConfig:
    """Default session settings."""
    model: str = "deepseek-r1-70b"
    gpu: str = "gpu_1x_a100_sxm4_80gb"
    lease_hours: int = 4


@dataclass
class SSHConfig:
    """SSH configuration."""
    key_path: str = "~/.ssh/id_rsa"


@dataclass
class CloudflareConfig:
    """Cloudflare API configuration."""
    api_token: str = ""
    account_id: str = ""
    kv_namespace_id: str = ""
    worker_url: str = ""
    worker_name: str = "gpu-watchdog"


@dataclass
class Config:
    """Complete configuration."""
    lambda_config: LambdaConfig
    status_daemon: StatusDaemonConfig
    defaults: DefaultsConfig = None
    ssh: SSHConfig = None
    cloudflare: CloudflareConfig = None
    custom_models: Dict[str, dict] = None

    def __post_init__(self):
        if self.defaults is None:
            self.defaults = DefaultsConfig()
        if self.ssh is None:
            self.ssh = SSHConfig()
        if self.cloudflare is None:
            self.cloudflare = CloudflareConfig()
        if self.custom_models is None:
            self.custom_models = {}


class ConfigManager:
    """Manage configuration file."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "gpu-dashboard"
        self.config_file = self.config_dir / "config.yaml"

    def load(self) -> Optional[Config]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return None

        with open(self.config_file) as f:
            data = yaml.safe_load(f)

        # Load custom_models and validate each one
        custom_models = data.get("custom_models", {})
        for model_id, model_data in custom_models.items():
            try:
                validate_custom_model(model_data)
            except ValueError as e:
                # Log warning but don't fail load
                import logging
                logging.warning(f"Invalid custom model '{model_id}': {e}")

        return Config(
            lambda_config=LambdaConfig(**data.get("lambda", {})),
            status_daemon=StatusDaemonConfig(**data.get("status_daemon", {})),
            defaults=DefaultsConfig(**data.get("defaults", {})),
            ssh=SSHConfig(**data.get("ssh", {})),
            cloudflare=CloudflareConfig(**data.get("cloudflare", {})),
            custom_models=custom_models,
        )

    def save(self, config: Config):
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "lambda": asdict(config.lambda_config),
            "status_daemon": asdict(config.status_daemon),
            "defaults": asdict(config.defaults),
            "ssh": asdict(config.ssh),
            "cloudflare": asdict(config.cloudflare),
            "custom_models": config.custom_models,
        }

        with open(self.config_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        # Secure permissions
        os.chmod(self.config_file, 0o600)

    def exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_file.exists()
