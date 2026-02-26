from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import Severity, Violation
from snowfort_audit.infrastructure.cortex_synthesizer import CortexSynthesizer


class TestAIFeatures:
    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        return MagicMock()

    def test_cortex_synthesis(self, mock_cursor):
        synthesizer = CortexSynthesizer(mock_cursor)

        violations = [
            Violation("COST_012", "q_123", "Isolation Pivot needed.", Severity.MEDIUM),
            Violation("PERF_006", "WH_LARGE", "Oversized. Save $100.", Severity.MEDIUM),
        ]

        # Mock Cortex SQL Output
        mock_cursor.fetchall.return_value = [("This account has significant cost saving opportunities...",)]

        summary = synthesizer.summarize(violations)

        assert "This account has significant cost saving opportunities" in summary
        # Verify SQL query contained the violations text
        args, _ = mock_cursor.execute.call_args
        query = args[0]
        assert "Isolation Pivot" in query
        assert "Oversized" in query
        assert "SNOWFLAKE.CORTEX.COMPLETE" in query
