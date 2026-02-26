"""Functional tests for snowfort login: run the login flow and verify exported session variables.

These tests invoke the login command (with scripted input), parse the export lines from stdout,
and assert that the resulting "session" has the correct variables for each auth method.
No real Snowflake connection or keyring is used; input is provided via mocked _ask.
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from snowfort_audit.interface.cli import (
    AUTH_DISPLAY_TO_SNOWFLAKE,
    main,
)


def parse_login_exports(stdout: str) -> dict[str, str]:
    """Parse 'export VAR=value' lines from login stdout into a dict of VAR -> value.

    Handles single- and double-quoted values and escaped quotes inside.
    """
    result = {}
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line.startswith("export "):
            continue
        rest = line[7:].strip()  # after "export "
        if "=" not in rest:
            continue
        name, _, value_part = rest.partition("=")
        name = name.strip()
        value_part = value_part.strip()
        if not value_part:
            result[name] = ""
            continue
        if value_part.startswith("'") and value_part.endswith("'"):
            value = value_part[1:-1].replace("\\'", "'")
        elif value_part.startswith('"') and value_part.endswith('"'):
            value = value_part[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        else:
            value = value_part
        result[name] = value
    return result


def _run_login_with_answers(
    runner: CliRunner,
    mock_container: MagicMock,
    answers: list[str],
    reset: bool = False,
) -> tuple[int, str, dict[str, str]]:
    """Invoke snowfort login with scripted answers; return exit_code, stdout, parsed exports."""
    args = ["login"]
    if reset:
        args.append("--reset")
    with patch("snowfort_audit.interface.cli._ask", side_effect=answers):
        result = runner.invoke(main, args, obj=mock_container)
    exports = parse_login_exports(result.output)
    return result.exit_code, result.output, exports


def _mock_config(get_env_return: dict[str, str] | None = None) -> MagicMock:
    config = MagicMock()
    if get_env_return is not None:
        config.get_env.side_effect = lambda k: get_env_return.get(k)
    else:
        config.get_env.return_value = None
    return config


def _mock_container(config: MagicMock) -> MagicMock:
    container = MagicMock()
    container.get.side_effect = lambda k: config if k == "ConfigurationProtocol" else MagicMock()
    return container


class TestParseLoginExports:
    """Test the export-line parser."""

    def test_parses_single_quoted(self) -> None:
        out = "export SNOWFLAKE_ACCOUNT='org-acc'\nexport SNOWFLAKE_USER='u1'"
        assert parse_login_exports(out) == {"SNOWFLAKE_ACCOUNT": "org-acc", "SNOWFLAKE_USER": "u1"}

    def test_parses_double_quoted(self) -> None:
        out = 'export SNOWFLAKE_ACCOUNT="org-acc"\nexport SNOWFLAKE_USER="u1"'
        assert parse_login_exports(out) == {"SNOWFLAKE_ACCOUNT": "org-acc", "SNOWFLAKE_USER": "u1"}

    def test_ignores_non_export_lines(self) -> None:
        out = "To set variables...\nexport SNOWFLAKE_ACCOUNT='a'\n\n"
        assert parse_login_exports(out) == {"SNOWFLAKE_ACCOUNT": "a"}

    def test_empty_stdout(self) -> None:
        assert parse_login_exports("") == {}
        assert parse_login_exports("\n\n") == {}


class TestLoginFlowBrowser:
    """Login flow with auth=browser: exports ACCOUNT, USER, ROLE, AUTHENTICATOR=externalbrowser."""

    def test_login_browser_sets_correct_vars(self) -> None:
        runner = CliRunner()
        config = _mock_config(None)
        container = _mock_container(config)
        answers = ["my-org.my-account", "myuser", "AUDITOR", "browser"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_ACCOUNT") == "my-org.my-account"
        assert exports.get("SNOWFLAKE_USER") == "myuser"
        assert exports.get("SNOWFLAKE_ROLE") == "AUDITOR"
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == AUTH_DISPLAY_TO_SNOWFLAKE["browser"]
        assert "SNOWFLAKE_PRIVATE_KEY_PATH" not in exports


class TestLoginFlowMfa:
    """Login flow with auth=mfa: exports AUTHENTICATOR=username_password_mfa, no key path."""

    def test_login_mfa_sets_correct_vars(self) -> None:
        runner = CliRunner()
        config = _mock_config(None)
        container = _mock_container(config)
        answers = ["acc", "u", "SYSADMIN", "mfa"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == AUTH_DISPLAY_TO_SNOWFLAKE["mfa"]
        assert "SNOWFLAKE_PRIVATE_KEY_PATH" not in exports


class TestLoginFlowKeypair:
    """Login flow with auth=keypair: exports AUTHENTICATOR=snowflake_jwt and SNOWFLAKE_PRIVATE_KEY_PATH."""

    def test_login_keypair_sets_correct_vars(self) -> None:
        runner = CliRunner()
        config = _mock_config(None)
        container = _mock_container(config)
        answers = ["acc", "u", "AUDITOR", "keypair", "/path/to/key.pem"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == AUTH_DISPLAY_TO_SNOWFLAKE["keypair"]
        assert exports.get("SNOWFLAKE_PRIVATE_KEY_PATH") == "/path/to/key.pem"


class TestLoginFlowPat:
    """Login flow with auth=pat: exports AUTHENTICATOR=snowflake (token as password)."""

    def test_login_pat_sets_correct_vars(self) -> None:
        runner = CliRunner()
        config = _mock_config(None)
        container = _mock_container(config)
        answers = ["acc", "u", "AUDITOR", "pat"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == AUTH_DISPLAY_TO_SNOWFLAKE["pat"]
        assert "SNOWFLAKE_PRIVATE_KEY_PATH" not in exports


class TestLoginFlowWithExistingEnv:
    """Login with --reset and with existing env: verify exports reflect chosen auth."""

    def test_login_reset_ignores_existing_uses_answers(self) -> None:
        runner = CliRunner()
        config = _mock_config(
            {
                "SNOWFLAKE_ACCOUNT": "old-acc",
                "SNOWFLAKE_USER": "old-user",
                "SNOWFLAKE_ROLE": "OLD_ROLE",
                "SNOWFLAKE_AUTHENTICATOR": "externalbrowser",
            }
        )
        container = _mock_container(config)
        answers = ["new-acc", "new-user", "AUDITOR", "mfa"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers, reset=True)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_ACCOUNT") == "new-acc"
        assert exports.get("SNOWFLAKE_USER") == "new-user"
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == "username_password_mfa"

    def test_login_no_reset_uses_existing_as_defaults_still_exports(self) -> None:
        runner = CliRunner()
        config = _mock_config(
            {
                "SNOWFLAKE_ACCOUNT": "org-acc",
                "SNOWFLAKE_USER": "u1",
                "SNOWFLAKE_ROLE": "AUDITOR",
                "SNOWFLAKE_AUTHENTICATOR": "externalbrowser",
            }
        )
        container = _mock_container(config)
        # User re-confirms same values (browser -> externalbrowser)
        answers = ["org-acc", "u1", "AUDITOR", "browser"]
        exit_code, _, exports = _run_login_with_answers(runner, container, answers)
        assert exit_code == 0
        assert exports.get("SNOWFLAKE_ACCOUNT") == "org-acc"
        assert exports.get("SNOWFLAKE_AUTHENTICATOR") == "externalbrowser"
