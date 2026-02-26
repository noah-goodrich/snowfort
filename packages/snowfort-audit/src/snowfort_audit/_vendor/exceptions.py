"""Minimal exception hierarchy (vendored)."""


class SnowarchError(Exception):
    """Base exception for Snowarch components."""


class InfrastructureError(SnowarchError):
    """General infrastructure failure."""
