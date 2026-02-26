"""Connection resolver (vendored)."""

from snowfort_audit._vendor.connection_models import AuthCredentials, ConnectionOptions
from snowfort_audit._vendor.protocols import ConfigurationProtocol, CredentialProtocol, TelemetryPort


def _resolve_password(
    config: ConfigurationProtocol,
    cred: CredentialProtocol,
    account: str | None,
    user: str | None,
    authenticator: str,
    interactive: bool,
) -> str | None:
    """Resolve password from env, keyring, or interactive prompt (used for mfa and pat)."""
    password = config.get_env("SNOWFLAKE_PASSWORD")
    if password:
        return password
    if authenticator not in ("snowflake", "username_password_mfa") or not account or not user:
        return None
    password = cred.get_stored_password(account, user)
    if not password and interactive:
        password = cred.get_password(account, user)
    return password


def _resolve_private_key_path(config: ConfigurationProtocol, authenticator: str) -> str | None:
    """Resolve private key path for keypair (snowflake_jwt) auth."""
    if authenticator != "snowflake_jwt":
        return None
    return config.get_env("SNOWFLAKE_PRIVATE_KEY_PATH") or None


def _resolve_passcode(
    config: ConfigurationProtocol,
    cred: CredentialProtocol,
    account: str | None,
    user: str | None,
    authenticator: str,
    interactive: bool,
) -> str | None:
    """Resolve MFA passcode from env or interactive prompt."""
    passcode = config.get_env("SNOWFLAKE_PASSCODE")
    if passcode is not None and not passcode.strip():
        passcode = None
    if passcode is not None:
        return passcode
    if authenticator != "username_password_mfa" or not account or not user or not interactive:
        return None
    return cred.get_passcode(account, user)


class ConnectionResolver:
    """Resolves Snowflake connection options from overrides, env, keyring, or prompts."""

    def __init__(
        self,
        cred_gateway: CredentialProtocol,
        telemetry: TelemetryPort,
        config_gateway: ConfigurationProtocol,
    ):
        self.cred_gateway = cred_gateway
        self.telemetry = telemetry
        self.config_gateway = config_gateway

    def resolve(
        self,
        account: str | None = None,
        user: str | None = None,
        role: str | None = None,
        authenticator: str | None = None,
        interactive: bool = True,
        default_role: str = "AUDITOR",
    ) -> ConnectionOptions:
        account = account or self.config_gateway.get_env("SNOWFLAKE_ACCOUNT")
        user = user or self.config_gateway.get_env("SNOWFLAKE_USER")
        role = role or self.config_gateway.get_env("SNOWFLAKE_ROLE")
        authenticator = authenticator or self.config_gateway.get_env("SNOWFLAKE_AUTHENTICATOR")

        if interactive and (not user or not account):
            self.telemetry.step("[yellow]Required Snowflake credentials missing.[/yellow]")
            if not account:
                account = self.telemetry.ask("Snowflake Account (org-account)")
            if not user:
                user = self.telemetry.ask("User")

        if interactive:
            if not role:
                role = self.telemetry.ask("Role", default=default_role)
            if not authenticator:
                authenticator = self.telemetry.ask(
                    "Authenticator (username_password_mfa, snowflake_jwt, snowflake)",
                    default="username_password_mfa",
                )

        if not authenticator:
            authenticator = "username_password_mfa"

        private_key_path = _resolve_private_key_path(self.config_gateway, authenticator)
        password = _resolve_password(
            self.config_gateway,
            self.cred_gateway,
            account,
            user,
            authenticator,
            interactive,
        )
        passcode = _resolve_passcode(
            self.config_gateway,
            self.cred_gateway,
            account,
            user,
            authenticator,
            interactive,
        )

        pk_path = (private_key_path or "").strip() or None
        auth_creds = AuthCredentials(
            password=password,
            passcode=passcode,
            private_key_path=pk_path,
        )
        return ConnectionOptions(
            account=(account or "").strip(),
            user=(user or "").strip(),
            role=role.strip() if role else role,
            authenticator=authenticator.strip() if authenticator else authenticator,
            auth=auth_creds,
        )
