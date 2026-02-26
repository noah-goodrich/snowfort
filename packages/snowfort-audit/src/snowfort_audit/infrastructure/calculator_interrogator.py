import logging
from typing import Any

from snowfort_audit.domain.protocols import CalculatorProtocol
from snowfort_audit.infrastructure.database_errors import SnowflakeConnectorError

logger = logging.getLogger(__name__)


class CalculatorInterrogator(CalculatorProtocol):
    """Interrogates Snowflake account for Pricing Calculator inputs."""

    def __init__(self, cursor: Any):
        self.cursor = cursor

    def get_inputs(self) -> dict[str, Any]:
        return {
            "storage": self._get_storage(),
            "compute": self._get_compute(),
            "data_transfer": self._get_data_transfer(),
        }

    def _get_storage(self) -> dict[str, float]:
        # Average storage over last 30 days
        query = """
        SELECT AVG(AVERAGE_DATABASE_BYTES + AVERAGE_FAILSAFE_BYTES + AVERAGE_STAGE_BYTES) / 1024 / 1024 / 1024 / 1024
        FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
        WHERE USAGE_DATE > DATEADD('day', -30, CURRENT_DATE())
        """
        try:
            self.cursor.execute(query)
            res = self.cursor.fetchall()
            return {"average_tb": float(res[0][0]) if res and res[0][0] else 0.0}
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Failed to get storage metrics: %s", e)
            return {"average_tb": 0.0}

    def _get_compute(self) -> dict[str, float]:
        # Total Credits / Hours per size (Last 30 Days)
        query = """
        SELECT
            WAREHOUSE_SIZE,
            SUM(CREDITS_USED) as TOTAL_CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
        GROUP BY 1
        """
        compute_map = {}
        try:
            self.cursor.execute(query)
            for row in self.cursor.fetchall():
                size = row[0]
                credits_used = row[1]
                if size:
                    compute_map[size] = float(credits_used)
            return compute_map
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Failed to get compute metrics: %s", e)
            return {}

    def _get_data_transfer(self) -> dict[str, float]:
        # Total GB transferred (Last 30 Days)
        query = """
        SELECT SUM(BYTES_TRANSFERRED) / 1024 / 1024 / 1024
        FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
        WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
        """
        try:
            self.cursor.execute(query)
            res = self.cursor.fetchall()
            return {"transfer_gb": float(res[0][0]) if res and res[0][0] else 0.0}
        except (SnowflakeConnectorError, RuntimeError) as e:
            logger.error("Failed to get data transfer metrics: %s", e)
            return {"transfer_gb": 0.0}
