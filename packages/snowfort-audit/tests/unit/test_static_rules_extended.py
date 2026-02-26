from unittest.mock import MagicMock, call

from snowfort_audit.domain.rules.static import SelectStarCheck


class TestSelectStarCheckExtended:
    def test_extract_sql_from_python_valid(self):
        validator = MagicMock()
        rule = SelectStarCheck(validator)

        content = """
query = "SELECT * FROM users"
other = "CREATE TABLE foo"
        """
        validator.validate.return_value = []

        rule.check_static(content, "test.py")

        # Verify that extraction worked by checking what was sent to validation

        expected_call_count = 2
        assert validator.validate.call_count == expected_call_count
        validator.validate.assert_has_calls([call("SELECT * FROM users"), call("CREATE TABLE foo")], any_order=True)

    def test_extract_sql_from_python_ast_error(self):
        validator = MagicMock()
        telemetry = MagicMock()
        rule = SelectStarCheck(validator, telemetry=telemetry)

        # Invalid python syntax
        content = "def invalid_syntax(:"

        violations = rule.check_static(content, "test.py")

        assert violations == []
        validator.validate.assert_not_called()
        telemetry.debug.assert_called_once()

    def test_check_static_python_dispatch(self):
        validator = MagicMock()
        rule = SelectStarCheck(validator)

        # Mock validator to return violations only for the SELECT *
        mock_violation = MagicMock()
        mock_violation.code = "AM04"
        mock_violation.description = "Select *"
        mock_violation.line = 1
        mock_violation.matches.return_value = True

        validator.validate.side_effect = lambda sql: [mock_violation] if "SELECT *" in sql else []

        content = """
def run():
    sql = "SELECT * FROM users"
        """

        violations = rule.check_static(content, "test.py")
        assert len(violations) == 1
        assert "Line" in violations[0].message

    def test_check_online_success(self):
        validator = MagicMock()
        rule = SelectStarCheck(validator)

        cursor = MagicMock()
        cursor.fetchone.return_value = ["CREATE VIEW v AS SELECT * FROM t"]

        # Dispatch to check_static -> extract (empty if not .py?) -> no, check_static logic:
        # if file_path.endswith(".py"): ... else: append((file_content, 1))

        mock_violation = MagicMock()
        mock_violation.code = "AM04"
        mock_violation.matches.return_value = True
        mock_violation.description = "Bad"
        mock_violation.line = 1
        validator.validate.return_value = [mock_violation]

        violations = rule.check_online(cursor, "MY_VIEW")
        assert len(violations) == 1
        cursor.execute.assert_called_with("SELECT GET_DDL('VIEW', 'MY_VIEW')")

    def test_check_online_no_resource(self):
        validator = MagicMock()
        rule = SelectStarCheck(validator)
        violations = rule.check_online(MagicMock(), None)
        assert violations == []

    def test_check_online_failure(self):
        validator = MagicMock()
        telemetry = MagicMock()
        rule = SelectStarCheck(validator, telemetry=telemetry)

        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("DB Error")

        violations = rule.check_online(cursor, "MY_VIEW")
        assert violations == []
        telemetry.error.assert_called_once()
