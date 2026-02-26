from unittest.mock import MagicMock

import pytest

from snowfort_audit.infrastructure.calculator_interrogator import CalculatorInterrogator


class TestCalculator:
    EXPECTED_STORAGE_TB = 10.0
    EXPECTED_COMPUTE_CREDITS_LARGE = 100.0
    EXPECTED_TRANSFER_GB = 500.0

    @pytest.fixture
    def mock_cursor(self) -> MagicMock:
        return MagicMock()

    def test_get_calculator_inputs(self, mock_cursor):
        calc = CalculatorInterrogator(mock_cursor)

        # Setup mocks for multiple method calls (storage, compute, transfer)
        # 1. Storage Query (Returns avg bytes)
        # 2. Compute Query (Returns rows of WH Size, Credits, Hours)
        # 3. Transfer Query (Returns GB)

        # We need to configure side_effect for execute to handle sequential queries?
        # Or just mock fetchall based on last call.
        # But Interrogator calls execute multiple times.
        # Simpler approach: Test individual methods if they existed, or mock side_effect.

        # Cursor.execute returns None. Cursor.fetchall returns data.
        # We can use side_effect on fetchall to return different data for each call.

        # Call 1 (Storage): 10 TB
        # Call 2 (Compute): [("Active Hours", "Large", 100.0), ("Active Hours", "Small", 50.0)]
        # Wait, compute query likely aggregates by size.
        # Call 3 (Transfer): 500 GB

        mock_cursor.fetchall.side_effect = [
            [(10.0,)],  # 10 TB (SQL calculated)
            [("LARGE", 100.0), ("SMALL", 50.0)],
            [(500.0,)],  # 500 GB (SQL calculated)
        ]

        result = calc.get_inputs()

        assert result["storage"]["average_tb"] == self.EXPECTED_STORAGE_TB
        assert result["compute"]["LARGE"] == self.EXPECTED_COMPUTE_CREDITS_LARGE
        assert result["data_transfer"]["transfer_gb"] == self.EXPECTED_TRANSFER_GB
