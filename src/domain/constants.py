"""Shared constants for the VNF placement domain model.

Keep only stable domain-level values here. Experiment settings such as the
learning rate, number of episodes, gamma and epsilon belong in
``experiments/configs/`` instead.
"""

from typing import Final


# Short keys used by Network and AllocationManager for server resources.
RESOURCE_TYPES: Final[tuple[str, ...]] = ("c", "r", "h")

# Human-readable names for logs, reports and error messages.
RESOURCE_NAMES: Final[dict[str, str]] = {
    "c": "CPU",
    "r": "RAM",
    "h": "HDD",
}

# Numerical tolerance for capacity and resource-underflow checks.
EPSILON: Final[float] = 1e-9
