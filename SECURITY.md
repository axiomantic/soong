# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email axiomantic@pm.me with details
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix timeline**: Depends on severity

## Security Best Practices

When using Soong:

- Store your Lambda API key securely (config file has 0600 permissions)
- Never commit API keys or tokens to version control
- Use SSH keys with passphrases
- Monitor your Lambda Labs billing for unexpected charges
- Set appropriate lease limits to control costs

## Scope

This security policy covers:

- The Soong CLI tool
- Configuration file handling
- API key management
- SSH tunnel implementation

Third-party services (Lambda Labs, etc.) have their own security policies.
