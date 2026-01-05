# Changelog

All notable changes to Soong will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Smart tunnel port allocation**: Automatically finds available local ports starting from configured defaults, incrementing by 1 if in use
- **Configurable tunnel ports**: New `tunnel` config section with `sglang_port`, `n8n_port`, `status_port` defaults
- **Recursive help**: `soong --help` now shows full manual with all commands, subcommands, and options
- **Automatic instance provisioning**: Ansible-based provisioning runs automatically after instance launch
- **Auto-start SSH tunnel**: Tunnel starts automatically when instance becomes ready
- **SSH key mismatch detection**: Suggests correct key when SSH fails due to key mismatch
- **Global instance history**: Track all GPU sessions via Cloudflare Worker with KV storage
- **Pre-launch validation**: Validates GPU availability, filesystem, SSH keys before launch
- **Prometheus metrics polling**: Status daemon detects activity via SGLang metrics instead of SSH

### Changed

- `soong tunnel` now defaults to starting the tunnel (same as `soong tunnel start`)
- Instance boot progress shows smoothly updating elapsed time
- Improved instance launch success output with service URLs

### Fixed

- Lambda API URL corrected for proper endpoint access
- `datetime.utcnow()` deprecation warnings resolved

## [0.1.0] - Initial Release

### Added

- Core CLI with `start`, `stop`, `status`, `ssh`, `tunnel`, `extend` commands
- Lambda Labs API integration for instance management
- Status daemon with idle detection and lease management
- Multi-layer cost protection (idle timeout, lease system, hard timeout, watchdog)
- Model registry with GPU recommendations and VRAM estimation
- Custom model support via configuration
- SSH tunnel management for secure service access
- Cloudflare Worker watchdog for external failsafe
- Rich terminal UI with tables, panels, and progress indicators
- Interactive configuration wizard
- MkDocs documentation site
