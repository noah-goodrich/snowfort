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
            Violation("COST_046", "q_123", "Isolation Pivot needed.", Severity.MEDIUM),
            Violation("PERF_006", "WH_LARGE", "Oversized. Save $100.", Severity.MEDIUM),
        ]

        mock_cursor.fetchall.return_value = [("This account has significant cost saving opportunities...",)]

        summary = synthesizer.summarize(violations)

        assert "This account has significant cost saving opportunities" in summary
        args, _ = mock_cursor.execute.call_args
        query, params = args[0], args[1]
        assert "SNOWFLAKE.CORTEX.COMPLETE(%s, %s)" in query
        assert params[0] == "mistral-large"
        prompt = params[1]
        assert "Isolation Pivot" in prompt
        assert "Oversized" in prompt
