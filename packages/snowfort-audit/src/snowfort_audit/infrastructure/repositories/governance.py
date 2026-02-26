from snowfort_audit._vendor.protocols import SnowflakeQueryProtocol
from snowfort_audit.domain.protocols import GovernanceProtocol


def _quote_id(name: str) -> str:
    """Quote identifier for Snowflake SQL (safe for role/user/warehouse names)."""
    return f'"{name}"'


class SnowflakeGovernanceRepository(GovernanceProtocol):
    """Repository for managing Snowflake governance (inline SQL, no core builders)."""

    def __init__(self, gateway: SnowflakeQueryProtocol):
        self._gateway = gateway

    def provision_auditor_role(self, role: str, user: str, warehouse: str) -> None:
        """Provisions the auditor role with inline DDL."""

        # 1. Create Role
        self._gateway.execute(f"CREATE ROLE IF NOT EXISTS {_quote_id(role)}")

        # 2. Grant Role to User
        self._gateway.execute(f"GRANT ROLE {_quote_id(role)} TO USER {_quote_id(user)}")

        # 3. Grant Imported Privileges on SNOWFLAKE Database
        self._gateway.execute(
            f"GRANT IMPORTED PRIVILEGES ON DATABASE {_quote_id('SNOWFLAKE')} TO ROLE {_quote_id(role)}"
        )

        # 4. Grant Usage on Warehouse
        self._gateway.execute(f"GRANT USAGE ON WAREHOUSE {_quote_id(warehouse)} TO ROLE {_quote_id(role)}")
