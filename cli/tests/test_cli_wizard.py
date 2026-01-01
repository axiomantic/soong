"""Tests for configure wizard warnings and cost estimates."""

import pytest
from unittest.mock import Mock, MagicMock
from rich.console import Console
from io import StringIO
from gpu_session.models import KNOWN_GPUS


def test_gpu_oversized_warning_shown(mocker):
    """Test that configure wizard shows warning when GPU is oversized (>1.5x needed)."""
    # Import the function we want to test (doesn't exist yet - will fail)
    from gpu_session.cli import show_gpu_size_warning

    # Capture console output
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)

    # Test scenario: deepseek-r1-70b needs ~48GB, user selects 80GB A100
    min_vram_needed = 48.0
    selected_vram = 80

    # Simulate viable GPUs list (sorted by price)
    viable_gpus = [
        {
            'type': Mock(name="gpu_1x_a6000", description="1x A6000 (48 GB)", format_price=lambda: "$0.80/hr"),
            'vram': 48,
            'available': True,
        },
        {
            'type': Mock(name="gpu_1x_a100_sxm4_80gb", description="1x A100 SXM4 (80 GB)", format_price=lambda: "$1.29/hr"),
            'vram': 80,
            'available': True,
        },
    ]

    default_gpu = "gpu_1x_a100_sxm4_80gb"  # User selected this

    # Call the function that should show the warning
    show_gpu_size_warning(
        console=test_console,
        selected_vram=selected_vram,
        min_vram_needed=min_vram_needed,
        viable_gpus=viable_gpus,
        selected_gpu=default_gpu,
    )

    result_output = output.getvalue()

    # Verify warning was shown
    assert "Note:" in result_output
    assert "A6000" in result_output
    assert "48" in result_output or "48GB" in result_output
    assert "would also work" in result_output
    assert "0.80" in result_output  # Check for price (ANSI codes may be present)


def test_no_warning_when_gpu_appropriately_sized(mocker):
    """Test no warning shown when GPU is the cheapest viable option."""
    from gpu_session.cli import show_gpu_size_warning
    from io import StringIO
    from rich.console import Console

    # Capture console output
    output = StringIO()
    test_console = Console(file=output, force_terminal=True)

    # Test scenario: User selects the cheapest viable GPU
    min_vram_needed = 48.0
    selected_vram = 48

    viable_gpus = [
        {
            'type': Mock(name="gpu_1x_a6000", description="1x A6000 (48 GB)", format_price=lambda: "$0.80/hr"),
            'vram': 48,
            'available': True,
        },
    ]

    selected_gpu = "gpu_1x_a6000"  # User selected the cheapest option

    # Call the function
    show_gpu_size_warning(
        console=test_console,
        selected_vram=selected_vram,
        min_vram_needed=min_vram_needed,
        viable_gpus=viable_gpus,
        selected_gpu=selected_gpu,
    )

    result_output = output.getvalue()

    # Should NOT show warning (user selected cheapest option)
    assert "Note:" not in result_output
    assert "would also work" not in result_output
