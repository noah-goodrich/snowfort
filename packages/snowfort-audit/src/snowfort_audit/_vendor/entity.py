"""Base Entity class (vendored)."""

from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity(ABC):
    """Immutable domain object. All domain entities should inherit from this."""
