# Reference Documentation

Complete technical reference for the `gpu-session` CLI tool.

## Documentation Sections

### [CLI Commands](cli-commands.md)
Comprehensive command reference with all flags, options, and examples.

### [Configuration File](configuration-file.md)
YAML configuration file schema, settings, and examples.

### [Model Registry](models.md)
Built-in AI models with VRAM requirements, quantization, and HuggingFace paths.

### [GPU Types](gpu-types.md)
Available GPU types with VRAM specifications and pricing information.

## Quick Links

- **Getting Started**: See the [Quick Start Guide](../getting-started/quick-start.md)
- **Configuration**: Run `gpu-session configure` or see [configuration reference](configuration-file.md)
- **Model Selection**: Use `gpu-session models` or see [model registry](models.md)
- **Available GPUs**: Check `gpu-session available` or see [GPU types](gpu-types.md)

## Configuration Location

The configuration file is stored at:

```
~/.config/gpu-dashboard/config.yaml
```

File permissions are automatically set to `0600` (owner read/write only) for security.

## API Integration

`gpu-session` uses the [Lambda Labs API](https://cloud.lambdalabs.com/api/v1/docs) for instance management. You'll need a Lambda Labs API key to use this tool.

## Version Information

This reference documentation is for `gpu-session` version 0.1.0+.
