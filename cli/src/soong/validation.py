"""Pre-launch validation for GPU instances."""

from typing import Optional, List, Tuple
from dataclasses import dataclass, field
import logging

from .lambda_api import LambdaAPI, InstanceType, FileSystem, LambdaAPIError
from .models import KNOWN_GPUS, get_model_config

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

    def _get_min_vram_for_model(self, model_id: Optional[str]) -> int:
        """Get minimum VRAM required for the given model, or 0 if unknown."""
        if not model_id:
            return 0
        config = get_model_config(model_id)
        if config:
            return config.min_vram_gb
        return 0

    def _get_gpu_vram(self, gpu_name: str) -> int:
        """Get VRAM for a GPU type from our known GPUs registry."""
        known = KNOWN_GPUS.get(gpu_name)
        if known:
            return known.get('vram_gb', 0)
        return 0

    def _find_alternative_gpus(
        self,
        min_vram: int,
        filesystem_region: Optional[str],
    ) -> List[Tuple[InstanceType, List[str]]]:
        """
        Find GPUs with capacity that meet VRAM requirements.

        Args:
            min_vram: Minimum VRAM needed (0 = any GPU)
            filesystem_region: If set, prioritize GPUs available in this region

        Returns:
            List of (InstanceType, compatible_regions) tuples, sorted by:
            1. Whether available in filesystem region
            2. Price (ascending)
        """
        instance_types = self._get_instance_types()
        alternatives: List[Tuple[InstanceType, List[str], bool]] = []

        for gpu in instance_types:
            if not gpu.regions_available:
                continue  # No capacity anywhere

            # Check VRAM requirement
            gpu_vram = self._get_gpu_vram(gpu.name)
            if min_vram > 0 and gpu_vram < min_vram:
                continue  # GPU too small

            # Check filesystem region compatibility
            in_fs_region = filesystem_region and filesystem_region in gpu.regions_available

            alternatives.append((gpu, gpu.regions_available, in_fs_region))

        # Sort: filesystem-compatible first, then by price
        alternatives.sort(key=lambda x: (not x[2], x[0].price_cents_per_hour))

        return [(gpu, regions) for gpu, regions, _ in alternatives]

    def _format_gpu_suggestion(
        self,
        gpu: InstanceType,
        regions: List[str],
        filesystem_region: Optional[str],
    ) -> str:
        """Format a single GPU suggestion with regions."""
        vram = self._get_gpu_vram(gpu.name)
        vram_str = f" ({vram}GB)" if vram > 0 else ""

        if filesystem_region and filesystem_region in regions:
            return f"{gpu.name}{vram_str} @ {gpu.format_price()} in {filesystem_region}"
        elif len(regions) <= 3:
            return f"{gpu.name}{vram_str} @ {gpu.format_price()} in {', '.join(regions)}"
        else:
            return f"{gpu.name}{vram_str} @ {gpu.format_price()} in {regions[0]} (+{len(regions)-1} more)"

    def validate(
        self,
        gpu_type: str,
        region: str,
        filesystem_name: Optional[str],
        ssh_key_names: List[str],
        model_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate all launch parameters.

        Args:
            gpu_type: GPU instance type name (e.g., "gpu_1x_gh200")
            region: Target region (e.g., "us-east-3")
            filesystem_name: Optional filesystem to attach
            ssh_key_names: SSH key names for instance access
            model_id: Optional model ID to check VRAM requirements

        Returns:
            ValidationResult with errors and warnings
        """
        errors: List[ValidationError] = []
        warnings: List[ValidationWarning] = []

        # Track filesystem region for GPU suggestions
        filesystem_region: Optional[str] = None

        # Validate SSH keys provided
        if not ssh_key_names:
            errors.append(ValidationError(
                message="No SSH keys provided",
                suggestion="At least one SSH key is required for instance access"
            ))
            return ValidationResult(errors=errors, warnings=warnings)

        # Deduplicate SSH keys (preserve order)
        ssh_key_names = list(dict.fromkeys(ssh_key_names))

        # Validate filesystem name format and get filesystem region
        if filesystem_name is not None:
            filesystem_name = filesystem_name.strip()
            if not filesystem_name:
                errors.append(ValidationError(
                    message="Filesystem name cannot be empty",
                    suggestion="Provide a valid filesystem name or omit the parameter"
                ))
                filesystem_name = None  # Skip further filesystem checks
            else:
                # Pre-fetch filesystem region for GPU suggestions
                try:
                    file_systems = self._get_file_systems()
                    fs = next((f for f in file_systems if f.name == filesystem_name), None)
                    if fs:
                        filesystem_region = fs.region
                except LambdaAPIError:
                    pass  # Will be caught in filesystem validation below

        # Get minimum VRAM requirement from model
        min_vram = self._get_min_vram_for_model(model_id)

        # GPU type validation with smart suggestions
        try:
            instance_types = self._get_instance_types()
            gpu = next((t for t in instance_types if t.name == gpu_type), None)

            if not gpu:
                errors.append(ValidationError(
                    message=f"GPU type '{gpu_type}' not found",
                    suggestion=f"Available: {self._format_available_gpus(instance_types)}"
                ))
            elif region not in gpu.regions_available:
                # GPU exists but no capacity in requested region
                if gpu.regions_available:
                    # GPU has capacity in other regions
                    compatible_regions = gpu.regions_available

                    # Check filesystem compatibility
                    if filesystem_region:
                        if filesystem_region in compatible_regions:
                            # Suggest the region where filesystem exists
                            errors.append(ValidationError(
                                message=f"No capacity for '{gpu_type}' in '{region}'",
                                suggestion=f"Use --region {filesystem_region} (matches your filesystem)"
                            ))
                        else:
                            # GPU available but not where filesystem is
                            # Find alternative GPUs in filesystem region
                            alternatives = self._find_alternative_gpus(min_vram, filesystem_region)
                            fs_compatible = [
                                (g, r) for g, r in alternatives
                                if filesystem_region in r and g.name != gpu_type
                            ]

                            if fs_compatible:
                                suggestions = [
                                    self._format_gpu_suggestion(g, r, filesystem_region)
                                    for g, r in fs_compatible[:3]
                                ]
                                errors.append(ValidationError(
                                    message=f"'{gpu_type}' not available in '{region}' or filesystem region '{filesystem_region}'",
                                    suggestion=f"Try: {'; '.join(suggestions)}"
                                ))
                            else:
                                errors.append(ValidationError(
                                    message=f"'{gpu_type}' available in {', '.join(compatible_regions)} but filesystem is in '{filesystem_region}'",
                                    suggestion=f"Either use --region {compatible_regions[0]} without filesystem, or choose different GPU"
                                ))
                    else:
                        # No filesystem constraint, just suggest available regions
                        errors.append(ValidationError(
                            message=f"No capacity for '{gpu_type}' in '{region}'",
                            suggestion=f"Available in: {', '.join(compatible_regions[:5])}"
                        ))
                else:
                    # GPU has no capacity anywhere - suggest alternatives
                    alternatives = self._find_alternative_gpus(min_vram, filesystem_region)

                    if alternatives:
                        suggestions = [
                            self._format_gpu_suggestion(g, r, filesystem_region)
                            for g, r in alternatives[:3]
                        ]
                        errors.append(ValidationError(
                            message=f"No capacity for '{gpu_type}' in any region",
                            suggestion=f"Alternatives: {'; '.join(suggestions)}"
                        ))
                    else:
                        errors.append(ValidationError(
                            message=f"No capacity for '{gpu_type}' in any region",
                            suggestion="No suitable alternatives found. Try again later."
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
