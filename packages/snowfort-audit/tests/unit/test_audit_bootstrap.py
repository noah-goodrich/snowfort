from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.models import BootstrapRequestDTO
from snowfort_audit.use_cases.bootstrap import BootstrapUseCase


@pytest.fixture
def telemetry() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="governance_repo")
def fixture_governance_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture(name="use_case")
def fixture_use_case(governance_repo, telemetry):
    return BootstrapUseCase(governance_repo, telemetry)


def test_bootstrap_execute_success(use_case, governance_repo):
    request = BootstrapRequestDTO(
        admin_role="SYSADMIN", auditor_role="AUDITOR", target_warehouse="COMPUTE_WH", target_user="TEST_USER"
    )

    use_case.execute(request)

    governance_repo.provision_auditor_role.assert_called_with(role="AUDITOR", user="TEST_USER", warehouse="COMPUTE_WH")
