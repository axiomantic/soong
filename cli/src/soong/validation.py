"""Pre-launch validation for GPU instances."""

from typing import Optional, List
from dataclasses import dataclass, field
import logging

from .lambda_api import LambdaAPI, InstanceType, FileSystem, LambdaAPIError

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Blocking validation error."""
    message: str
    suggestion: str


@dataclass
class ValidationWarning:
    """Non-blocking validation warning."""
    message: str
    suggestion: str


@dataclass
class ValidationResult:
    """Result of pre-launch validation."""
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)

    @property
    def can_launch(self) -> bool:
        """True if no blocking errors."""
        return len(self.errors) == 0


class LaunchValidator:
    """
    Validates launch parameters before calling Lambda API.

    Usage:
        validator = LaunchValidator(api)  # New instance per validation
        result = validator.validate(gpu, region, filesystem, ssh_keys)
        if not result.can_launch:
            # Show errors and exit

    Caching: API responses are cached for the lifetime of this instance
    (i.e., one validation run). Create a new instance for fresh data.
    """

    MAX_SUGGESTIONS = 5  # Max GPU types to show in error messages

    def __init__(self, api: LambdaAPI):
        self.api = api
        self._instance_types: Optional[List[InstanceType]] = None
        self._file_systems: Optional[List[FileSystem]] = None
        self._ssh_keys: Optional[List[str]] = None

    def _get_instance_types(self) -> List[InstanceType]:
        """Get instance types, cached for this validator instance."""
        if self._instance_types is None:
            self._instance_types = self.api.list_instance_types()
        return self._instance_types

    def _get_file_systems(self) -> List[FileSystem]:
        """Get filesystems, cached for this validator instance."""
        if self._file_systems is None:
            self._file_systems = self.api.list_file_systems()
        return self._file_systems

    def _get_ssh_keys(self) -> List[str]:
        """Get SSH keys, cached for this validator instance."""
        if self._ssh_keys is None:
            self._ssh_keys = self.api.list_ssh_keys()
        return self._ssh_keys

    def _format_available_gpus(self, instance_types: List[InstanceType]) -> str:
        """Format available GPU types for error messages."""
        if not instance_types:
            return "none available"

        gpu_names = [t.name for t in instance_types]

        if len(gpu_names) <= self.MAX_SUGGESTIONS:
            return ', '.join(gpu_names)
        else:
            shown = ', '.join(gpu_names[:self.MAX_SUGGESTIONS])
            remaining = len(gpu_names) - self.MAX_SUGGESTIONS
            return f"{shown}... ({remaining} more)"

    def validate(
        self,
        gpu_type: str,
        region: str,
        filesystem_name: Optional[str],
        ssh_key_names: List[str],
    ) -> ValidationResult:
        """
        Validate all launch parameters.

        Args:
            gpu_type: GPU instance type name (e.g., "gpu_1x_gh200")
            region: Target region (e.g., "us-east-3")
            filesystem_name: Optional filesystem to attach
            ssh_key_names: SSH key names for instance access

        Returns:
            ValidationResult with errors and warnings
        """
        errors: List[ValidationError] = []
        warnings: List[ValidationWarning] = []

        # Validate SSH keys provided
        if not ssh_key_names:
            errors.append(ValidationError(
                message="No SSH keys provided",
                suggestion="At least one SSH key is required for instance access"
            ))
            return ValidationResult(errors=errors, warnings=warnings)

        # Deduplicate SSH keys (preserve order)
        ssh_key_names = list(dict.fromkeys(ssh_key_names))

        # Validate filesystem name format
        if filesystem_name is not None:
            filesystem_name = filesystem_name.strip()
            if not filesystem_name:
                errors.append(ValidationError(
                    message="Filesystem name cannot be empty",
                    suggestion="Provide a valid filesystem name or omit the parameter"
                ))
                filesystem_name = None  # Skip further filesystem checks

        # GPU type validation (with graceful degradation)
        try:
            instance_types = self._get_instance_types()
            gpu = next((t for t in instance_types if t.name == gpu_type), None)
            if not gpu:
                errors.append(ValidationError(
                    message=f"GPU type '{gpu_type}' not found",
                    suggestion=f"Available: {self._format_available_gpus(instance_types)}"
                ))
            elif region not in gpu.regions_available:
                if gpu.regions_available:
                    warnings.append(ValidationWarning(
                        message=f"No capacity for '{gpu_type}' in '{region}'",
                        suggestion=f"Available in: {', '.join(gpu.regions_available)}"
                    ))
                else:
                    warnings.append(ValidationWarning(
                        message=f"No current capacity for '{gpu_type}' in any region",
                        suggestion="Try again later or choose a different GPU type"
                    ))
        except LambdaAPIError as e:
            logger.warning(f"GPU validation failed (API error): {e}")
            warnings.append(ValidationWarning(
                message="Could not validate GPU type (API error)",
                suggestion="Launch may fail if GPU type is invalid"
            ))

        # Filesystem validation (with graceful degradation)
        if filesystem_name:
            try:
                file_systems = self._get_file_systems()
                fs = next((f for f in file_systems if f.name == filesystem_name), None)
                if not fs:
                    available = ', '.join(f.name for f in file_systems) or "none"
                    errors.append(ValidationError(
                        message=f"Filesystem '{filesystem_name}' not found",
                        suggestion=f"Available filesystems: {available}"
                    ))
                elif fs.region != region:
                    errors.append(ValidationError(
                        message=f"Filesystem '{filesystem_name}' is in '{fs.region}', not '{region}'",
                        suggestion=f"Use --region {fs.region} or create filesystem in {region}"
                    ))
            except LambdaAPIError as e:
                logger.warning(f"Filesystem validation failed (API error): {e}")
                warnings.append(ValidationWarning(
                    message="Could not validate filesystem (API error)",
                    suggestion=f"Launch may fail if '{filesystem_name}' doesn't exist in '{region}'"
                ))

        # SSH key validation (with graceful degradation)
        try:
            ssh_keys = self._get_ssh_keys()
            for key in ssh_key_names:
                if key not in ssh_keys:
                    errors.append(ValidationError(
                        message=f"SSH key '{key}' not found",
                        suggestion="Add at: https://cloud.lambda.ai/ssh-keys"
                    ))
        except LambdaAPIError as e:
            logger.warning(f"SSH key validation failed (API error): {e}")
            warnings.append(ValidationWarning(
                message="Could not validate SSH keys (API error)",
                suggestion="Launch may fail if SSH keys are invalid"
            ))

        return ValidationResult(errors=errors, warnings=warnings)
