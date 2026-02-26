"""Tests for _vendor modules (configuration, telemetry, exceptions, entity, filesystem, connection_models, container, credentials, connection)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from snowfort_audit._vendor.configuration import EnvConfigurationGateway
from snowfort_audit._vendor.connection import ConnectionResolver
from snowfort_audit._vendor.connection_models import AuthCredentials, ConnectionOptions
from snowfort_audit._vendor.credentials import KeyringCredentialGateway
from snowfort_audit._vendor.entity import Entity
from snowfort_audit._vendor.exceptions import InfrastructureError, SnowarchError
from snowfort_audit._vendor.filesystem import LocalFileSystemGateway
from snowfort_audit._vendor.telemetry import RichTelemetry


# --- configuration ---
def test_env_configuration_gateway_get_env_missing():
    assert EnvConfigurationGateway().get_env("NONEXISTENT_VAR_XYZ") is None


def test_env_configuration_gateway_get_env_with_default():
    assert EnvConfigurationGateway().get_env("MISSING", default="fallback") == "fallback"


def test_env_configuration_gateway_get_env_set(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "value")
    assert EnvConfigurationGateway().get_env("TEST_VAR") == "value"


# --- telemetry ---
def test_rich_telemetry_step(capsys):
    t = RichTelemetry(project_name="T", color="cyan", welcome_msg="Hi")
    t.step("message")
    out, _ = capsys.readouterr()
    assert "message" in out


def test_rich_telemetry_error(capsys):
    t = RichTelemetry()
    t.error("err")
    out, _ = capsys.readouterr()
    assert "err" in out


def test_rich_telemetry_warning(capsys):
    t = RichTelemetry()
    t.warning("warn")
    out, _ = capsys.readouterr()
    assert "warn" in out


def test_rich_telemetry_handshake(capsys):
    t = RichTelemetry(project_name="Snowfort", color="cyan", welcome_msg="WAF Audit")
    t.handshake()
    out, _ = capsys.readouterr()
    assert "Snowfort" in out and "WAF Audit" in out


def test_rich_telemetry_ask():
    t = RichTelemetry()
    with patch("snowfort_audit._vendor.telemetry.Prompt") as mock_prompt:
        mock_prompt.ask.return_value = "answered"
        assert t.ask("Prompt?", default="") == "answered"


def test_rich_telemetry_confirm():
    t = RichTelemetry()
    with patch("snowfort_audit._vendor.telemetry.Confirm") as mock_confirm:
        mock_confirm.ask.return_value = True
        assert t.confirm("Proceed?") is True


def test_rich_telemetry_debug_prints_when_log_level_debug(capsys):
    t = RichTelemetry(log_level="DEBUG")
    t.debug("debug message")
    out, _ = capsys.readouterr()
    assert "debug message" in out


def test_rich_telemetry_debug_silent_when_log_level_info(capsys):
    t = RichTelemetry(log_level="INFO")
    t.debug("debug message")
    out, _ = capsys.readouterr()
    assert "debug message" not in out


def test_rich_telemetry_info_prints_when_log_level_info(capsys):
    t = RichTelemetry(log_level="INFO")
    t.info("info message")
    out, _ = capsys.readouterr()
    assert "info message" in out


def test_rich_telemetry_info_silent_when_log_level_warning(capsys):
    t = RichTelemetry(log_level="WARNING")
    t.info("info message")
    out, _ = capsys.readouterr()
    assert "info message" not in out


def test_rich_telemetry_set_log_level(capsys):
    t = RichTelemetry(log_level="WARNING")
    t.debug("before")
    t.set_log_level("DEBUG")
    t.debug("after")
    out, _ = capsys.readouterr()
    assert "before" not in out
    assert "after" in out


# --- exceptions ---
def test_snowarch_error():
    e = SnowarchError("msg")
    assert str(e) == "msg"
    assert isinstance(e, Exception)


def test_infrastructure_error():
    e = InfrastructureError("infra")
    assert isinstance(e, SnowarchError)


# --- entity ---
def test_entity_subclass():
    class ConcreteEntity(Entity):
        pass

    e = ConcreteEntity()
    assert isinstance(e, Entity)


# --- connection_models ---
def test_auth_credentials():
    a = AuthCredentials(password="p", passcode="c", private_key_path="/k")
    assert a.password == "p"
    assert a.passcode == "c"
    assert a.private_key_path == "/k"


def test_connection_options():
    auth = AuthCredentials(password="secret")
    opts = ConnectionOptions(account="org-acc", user="u", auth=auth, role="R", warehouse="W", authenticator="ext")
    assert opts.account == "org-acc"
    assert opts.role == "R"
    assert opts.auth.password == "secret"


# --- filesystem ---
def test_local_filesystem_gateway_exists(tmp_path):
    fs = LocalFileSystemGateway()
    assert fs.exists(str(tmp_path)) is True
    assert fs.exists(str(tmp_path / "nonexistent")) is False


def test_local_filesystem_gateway_read_write_text(tmp_path):
    fs = LocalFileSystemGateway()
    p = tmp_path / "f.txt"
    p.write_text("hello", encoding="utf-8")
    assert fs.read_text(str(p)) == "hello"
    fs.write_text(str(tmp_path / "out.txt"), "world")
    assert (tmp_path / "out.txt").read_text() == "world"


def test_local_filesystem_gateway_join_path():
    fs = LocalFileSystemGateway()
    assert "a" in fs.join_path("a", "b")
    assert "b" in fs.join_path("a", "b")


def test_local_filesystem_gateway_walk(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f.txt").write_text("x")
    fs = LocalFileSystemGateway()
    roots = list(fs.walk(str(tmp_path)))
    assert len(roots) >= 1
    dirs = roots[0][1]
    files = roots[0][2]
    assert "sub" in dirs or "f.txt" in files or any("f.txt" in r[2] for r in roots)


def test_local_filesystem_gateway_make_dirs_get_cwd_is_dir_get_parent(tmp_path):
    fs = LocalFileSystemGateway()
    d = tmp_path / "a" / "b"
    fs.make_dirs(str(d))
    assert d.is_dir()
    assert Path(fs.get_cwd()).is_dir()
    assert fs.is_dir(str(tmp_path)) is True
    assert fs.get_parent(str(tmp_path / "x")) == str(tmp_path)


# --- container (vendor BaseContainer) ---
def test_base_container_full_init_and_get():
    """Real BaseContainer runs _register_defaults; get() resolves singletons and factories."""
    from snowfort_audit._vendor.container import BaseContainer

    c = BaseContainer()
    assert c.get("FileSystemProtocol") is not None
    assert c.get("ConfigurationProtocol") is not None
    assert c.get("CredentialProtocol") is not None
    # Factory: each get() invokes the factory
    q1 = c.get("SnowflakeQueryProtocol")
    q2 = c.get("SnowflakeQueryProtocol")
    assert q1 is not None and q2 is not None


def test_base_container_register_and_get():
    from snowfort_audit._vendor.container import BaseContainer

    with patch.object(BaseContainer, "_register_defaults", lambda self: None):
        c = BaseContainer.__new__(BaseContainer)
        c._singletons = {}
        c._factories = {}
        c.register_singleton("K", 42)
        assert c.get("K") == 42


def test_base_container_factory():
    from snowfort_audit._vendor.container import BaseContainer

    with patch.object(BaseContainer, "_register_defaults", lambda self: None):
        c = BaseContainer.__new__(BaseContainer)
        c._singletons = {}
        c._factories = {}
        c.register_factory("F", lambda: "created")
        assert c.get("F") == "created"


def test_base_container_get_raises_when_missing():
    from snowfort_audit._vendor.container import BaseContainer

    with patch.object(BaseContainer, "_register_defaults", lambda self: None):
        c = BaseContainer.__new__(BaseContainer)
        c._singletons = {}
        c._factories = {}
        with pytest.raises(ValueError, match="not registered"):
            c.get("MISSING")


def test_base_container_register_telemetry():
    from snowfort_audit._vendor.container import BaseContainer

    with patch.object(BaseContainer, "_register_defaults", lambda self: None):
        c = BaseContainer.__new__(BaseContainer)
        c._singletons = {}
        c._factories = {}
        c.register_telemetry(project_name="P", color="cyan", welcome_msg="W")
        assert c.get("TelemetryPort") is not None


# --- credentials ---
def test_keyring_credential_gateway_get_stored_password():
    with patch("snowfort_audit._vendor.credentials.keyring.get_password", return_value=None):
        g = KeyringCredentialGateway()
        assert g.get_stored_password("acc", "user") is None


def test_keyring_credential_gateway_get_passcode():
    with patch("snowfort_audit._vendor.credentials.Prompt") as mock_prompt:
        mock_prompt.ask.return_value = "654321"
        g = KeyringCredentialGateway()
        assert g.get_passcode("acc", "user") == "654321"
        mock_prompt.ask.assert_called_once()
        call_kw = mock_prompt.ask.call_args[1]
        assert call_kw.get("password") is True
        assert "passcode" in str(mock_prompt.ask.call_args[0][0]).lower()


def test_keyring_credential_gateway_get_passcode_empty_returns_none():
    with patch("snowfort_audit._vendor.credentials.Prompt") as mock_prompt:
        mock_prompt.ask.return_value = ""
        g = KeyringCredentialGateway()
        assert g.get_passcode("acc", "user") is None


def test_keyring_credential_gateway_clear_credentials():
    with patch("snowfort_audit._vendor.credentials.keyring.delete_password"):
        g = KeyringCredentialGateway()
        g.clear_credentials("acc", "user")


def test_keyring_credential_gateway_get_password_prompts_when_not_stored():
    with patch("snowfort_audit._vendor.credentials.keyring.get_password", return_value=None):
        with patch("snowfort_audit._vendor.credentials.Prompt.ask", return_value="entered_pw"):
            with patch("snowfort_audit._vendor.credentials.keyring.set_password"):
                g = KeyringCredentialGateway()
                pw = g.get_password("my-acc", "myuser")
                assert pw == "entered_pw"


# --- connection resolver ---
def test_connection_resolver_resolve_non_interactive():
    mock_cred = MagicMock()
    mock_cred.get_stored_password.return_value = None
    mock_telemetry = MagicMock()
    mock_config = MagicMock()
    mock_config.get_env.side_effect = lambda k, default=None: {
        "SNOWFLAKE_ACCOUNT": "org-acc",
        "SNOWFLAKE_USER": "u",
        "SNOWFLAKE_ROLE": "R",
        "SNOWFLAKE_AUTHENTICATOR": "externalbrowser",
        "SNOWFLAKE_PASSWORD": None,
    }.get(k, default)
    r = ConnectionResolver(mock_cred, mock_telemetry, mock_config)
    opts = r.resolve(interactive=False, default_role="AUDITOR")
    assert opts.account == "org-acc"
    assert opts.user == "u"
    assert opts.role == "R"
    mock_telemetry.ask.assert_not_called()


def test_connection_resolver_resolve_with_overrides():
    mock_cred = MagicMock()
    mock_telemetry = MagicMock()
    mock_config = MagicMock()
    mock_config.get_env.return_value = None
    r = ConnectionResolver(mock_cred, mock_telemetry, mock_config)
    opts = r.resolve(account="a", user="u", role="r", authenticator="ext", interactive=False)
    assert opts.account == "a"
    assert opts.user == "u"
    assert opts.role == "r"
    assert opts.authenticator == "ext"


def test_connection_resolver_resolve_interactive_missing_account_user():
    mock_cred = MagicMock()
    mock_cred.get_stored_password.return_value = None
    mock_telemetry = MagicMock()
    mock_telemetry.ask.side_effect = ["org-acc", "myuser", "AUDITOR", "externalbrowser"]
    mock_config = MagicMock()
    mock_config.get_env.return_value = None
    r = ConnectionResolver(mock_cred, mock_telemetry, mock_config)
    opts = r.resolve(interactive=True, default_role="AUDITOR")
    assert opts.account == "org-acc"
    assert opts.user == "myuser"
    assert opts.role == "AUDITOR"
    mock_telemetry.step.assert_called()
    assert mock_telemetry.ask.call_count >= 4


def test_connection_resolver_resolve_snowflake_auth_uses_stored_password():
    mock_cred = MagicMock()
    mock_cred.get_stored_password.return_value = "stored_secret"
    mock_telemetry = MagicMock()
    mock_config = MagicMock()
    mock_config.get_env.side_effect = lambda k, default=None: {
        "SNOWFLAKE_ACCOUNT": "org-acc",
        "SNOWFLAKE_USER": "u",
        "SNOWFLAKE_ROLE": "R",
        "SNOWFLAKE_AUTHENTICATOR": "snowflake",
        "SNOWFLAKE_PASSWORD": None,
    }.get(k, default)
    r = ConnectionResolver(mock_cred, mock_telemetry, mock_config)
    opts = r.resolve(interactive=False)
    assert opts.auth.password == "stored_secret"
    mock_cred.get_stored_password.assert_called_with("org-acc", "u")


def test_connection_resolver_resolve_username_password_mfa_prompts_passcode():
    """When authenticator is username_password_mfa and interactive, get_passcode is called and passcode is in auth."""
    mock_cred = MagicMock()
    mock_cred.get_stored_password.return_value = "stored_secret"
    mock_cred.get_passcode.return_value = "123456"
    mock_telemetry = MagicMock()
    mock_config = MagicMock()
    mock_config.get_env.side_effect = lambda k, default=None: {
        "SNOWFLAKE_ACCOUNT": "org-acc",
        "SNOWFLAKE_USER": "u",
        "SNOWFLAKE_ROLE": "R",
        "SNOWFLAKE_AUTHENTICATOR": "username_password_mfa",
    }.get(k, default)
    r = ConnectionResolver(mock_cred, mock_telemetry, mock_config)
    opts = r.resolve(interactive=True, default_role="AUDITOR")
    assert opts.auth.password == "stored_secret"
    assert opts.auth.passcode == "123456"
    mock_cred.get_passcode.assert_called_once_with("org-acc", "u")


# --- snowflake_gateway (vendor) ---
def test_normalize_account_from_url():
    from snowfort_audit._vendor.snowflake_gateway import _normalize_account

    assert _normalize_account("https://dyb56910.snowflakecomputing.com") == "dyb56910"
    assert _normalize_account("https://org-acc.snowflakecomputing.com") == "org-acc"
    assert _normalize_account("dyb56910") == "dyb56910"
    assert _normalize_account(None) is None
    assert _normalize_account("") is None


def test_snowflake_gateway_init():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    g = SnowflakeGateway(None)
    assert g.options is None
    assert g._connection is None


def test_snowflake_gateway_connect_raises_without_options():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    g = SnowflakeGateway(None)
    with pytest.raises(ValueError, match="No connection options"):
        g.connect()


def test_snowflake_gateway_connect_with_dict():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    with patch("snowfort_audit._vendor.snowflake_gateway.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        g = SnowflakeGateway({"account": "a", "user": "u", "password": "p"})
        g.connect()
        mock_connect.assert_called_once()
        assert g._connection is mock_conn


def test_snowflake_gateway_get_cursor():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    with patch("snowfort_audit._vendor.snowflake_gateway.connect", return_value=mock_conn):
        g = SnowflakeGateway({"account": "a", "user": "u"})
        cur = g.get_cursor()
        assert cur is mock_cursor


def test_snowflake_gateway_execute():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    with patch("snowfort_audit._vendor.snowflake_gateway.connect", return_value=mock_conn):
        g = SnowflakeGateway({"account": "a", "user": "u"})
        result = g.execute("SELECT 1")
        assert result is mock_cursor
        mock_cursor.execute.assert_called_once_with("SELECT 1", None)


def test_snowflake_gateway_execute_ddl_builder():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    builder = MagicMock()
    builder.build.return_value = "CREATE TABLE T (C INT)"
    with patch("snowfort_audit._vendor.snowflake_gateway.connect", return_value=mock_conn):
        g = SnowflakeGateway({"account": "a", "user": "u"})
        g.execute_ddl(builder)
        mock_cursor.execute.assert_called_with("CREATE TABLE T (C INT)", None)


def test_snowflake_gateway_execute_ddl_no_build_raises():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    g = SnowflakeGateway(None)
    with pytest.raises(ValueError, match="does not have a build"):
        g.execute_ddl(MagicMock(spec=[]))


def test_snowflake_gateway_close():
    from snowfort_audit._vendor.snowflake_gateway import SnowflakeGateway

    mock_conn = MagicMock()
    with patch("snowfort_audit._vendor.snowflake_gateway.connect", return_value=mock_conn):
        g = SnowflakeGateway({"account": "a", "user": "u"})
        g.connect()
        g.close()
        mock_conn.close.assert_called_once()
        assert g._connection is None
