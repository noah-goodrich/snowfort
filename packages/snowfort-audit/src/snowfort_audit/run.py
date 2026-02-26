"""Application bootstrap: creates a wired container. Used by Streamlit and tests."""

from snowfort_audit.di.container import AuditContainer
from snowfort_audit.infrastructure.wiring import register_all


def get_wired_container() -> AuditContainer:
    """Create an AuditContainer and register all Infrastructure and UseCase dependencies."""
    container = AuditContainer()
    register_all(container)
    return container
