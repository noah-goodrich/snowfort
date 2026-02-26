from snowfort_audit.domain.models import BootstrapRequestDTO
from snowfort_audit.domain.protocols import GovernanceProtocol, TelemetryPort


class BootstrapUseCase:
    """
    Provisions the AUDITOR role with necessary privileges.
    """

    def __init__(self, governance_repo: GovernanceProtocol, telemetry: TelemetryPort):
        self._governance_repo = governance_repo
        self.telemetry = telemetry

    def execute(self, request: BootstrapRequestDTO) -> None:
        """Executes the provisioning logic."""
        self.telemetry.step(f"Provisioning Prime Directive: Establishing AUDITOR role for {request.auditor_role}...")
        self._governance_repo.provision_auditor_role(
            role=request.auditor_role, user=request.target_user, warehouse=request.target_warehouse
        )
