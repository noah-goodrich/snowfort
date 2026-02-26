"""Thin CLI entry point: groups, shared helpers, calculator-inputs, rules. Scan/show/bootstrap live in submodules."""
# Warnings must run before importing click/rich (which can pull in requests). Ruff sees imports below as E402.
# ruff: noqa: E402

import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", module="snowflake.connector.vendored.requests")
warnings.filterwarnings("ignore", module="requests")

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from snowfort_audit.domain.account_config import (
    ACCOUNT_TOPOLOGY_MULTI_ENV,
    ACCOUNT_TOPOLOGY_ONE_PER_ACCOUNT,
    DEFAULT_ENVIRONMENTS,
)
from snowfort_audit.domain.dtos import ConnectionOptions
from snowfort_audit.interface.cli.report import conventions_for_pillar
from snowfort_audit.interface.constants import SNOWFORT_HEADER_MINIFIED, get_snowfort_splash

# Auth display names (CLI) -> Snowflake connector authenticator value.
AUTH_DISPLAY_CHOICES = ("mfa", "keypair", "pat", "browser")
AUTH_DISPLAY_TO_SNOWFLAKE = {
    "browser": "externalbrowser",
    "mfa": "username_password_mfa",
    "keypair": "snowflake_jwt",
    "pat": "snowflake",
}
AUTH_SNOWFLAKE_TO_DISPLAY = {v: k for k, v in AUTH_DISPLAY_TO_SNOWFLAKE.items()}


def _login_export_lines(
    account: str,
    user: str,
    role: str,
    authenticator: str,
    private_key_path: str,
) -> list[str]:
    """Build shell export lines for snowfort login."""
    lines = []
    if account:
        lines.append(f"export SNOWFLAKE_ACCOUNT={_sh_escape(account)}")
    if user:
        lines.append(f"export SNOWFLAKE_USER={_sh_escape(user)}")
    if role:
        lines.append(f"export SNOWFLAKE_ROLE={_sh_escape(role)}")
    if authenticator:
        lines.append(f"export SNOWFLAKE_AUTHENTICATOR={_sh_escape(authenticator)}")
    if authenticator == "snowflake_jwt" and private_key_path:
        lines.append(f"export SNOWFLAKE_PRIVATE_KEY_PATH={_sh_escape(private_key_path)}")
    return lines


def _get_telemetry(container):
    return container.get("TelemetryPort")


def get_connection_options(
    container,
    interactive: bool = True,
    account_override: str | None = None,
    user_override: str | None = None,
    role_override: str | None = None,
    authenticator_override: str | None = None,
) -> ConnectionOptions:
    """Gather Snowflake connection options from overrides, environment or user prompt."""
    resolver = container.get("ConnectionResolver")
    return resolver.resolve(
        account=account_override,
        user=user_override,
        role=role_override,
        authenticator=authenticator_override,
        interactive=interactive,
        default_role="AUDITOR",
    )


def _connection_error_hint(exc: BaseException) -> str | None:
    """Return a short hint for SAML/browser auth connection failures, or None."""
    msg = str(exc).lower()
    if "saml" not in msg and "390190" not in msg:
        return None
    return (
        "Your account may use SAML/SSO: try 'mfa' or 'keypair' auth, or set SNOWFLAKE_AUTHENTICATOR "
        "to your IdP URL (Snowflake Admin → Security → Authentication). "
        "For browser auth without a display, set SNOWFLAKE_AUTH_FORCE_SERVER_URL=1 and open the printed URL."
    )


def _warn_externalbrowser_headless(options: ConnectionOptions, telemetry: Any) -> None:
    auth = getattr(options, "authenticator", None) or ""
    if auth.strip().lower() != "externalbrowser":
        return
    if os.environ.get("DISPLAY"):
        return
    telemetry.warning(
        "No DISPLAY set; external browser auth may hang. "
        "Use keypair/password auth (e.g. SNOWFLAKE_AUTHENTICATOR=username_password_mfa) "
        "or run from a machine with a browser."
    )


def _prompt_account_config(project_root: Path) -> dict[str, Any]:
    click.echo("Snowfort account context (saved to .snowfort/config.yml for future runs)")
    topo = click.prompt(
        "Do you use one Snowflake account per environment, or multiple environments in one account?",
        type=click.Choice([ACCOUNT_TOPOLOGY_ONE_PER_ACCOUNT, ACCOUNT_TOPOLOGY_MULTI_ENV], case_sensitive=False),
        default=ACCOUNT_TOPOLOGY_MULTI_ENV,
    )
    env_default = ",".join(DEFAULT_ENVIRONMENTS)
    env_str = click.prompt(
        "Environment prefixes (comma-separated)",
        default=env_default,
        show_default=True,
    )
    environments = [e.strip().upper() for e in env_str.split(",") if e.strip()]
    if not environments:
        environments = list(DEFAULT_ENVIRONMENTS)
    return {"account_topology": topo, "environments": environments}


def _sh_escape(value: str) -> str:
    if "'" in value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return "'" + value + "'"


def _ask(prompt: str, default: str, use_stderr: bool) -> str:
    if use_stderr:
        return Prompt.ask(prompt, default=default, console=Console(stderr=True))
    return Prompt.ask(prompt, default=default)


@click.group(
    help=f"{SNOWFORT_HEADER_MINIFIED}\n\nUsage: snowfort audit [OPTIONS] COMMAND [ARGS]...",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def main():
    """Snowfort – Snowflake architecture tools. Use 'snowfort audit' for WAF compliance."""
    pass


@main.group(
    "audit",
    help=f"{SNOWFORT_HEADER_MINIFIED}\n\nWAF Policy Compliance – scan, show, rules, bootstrap, demo-setup.",
    invoke_without_command=True,
)
@click.pass_context
def audit(ctx):
    """Audit subcommand: scan, show, rules, bootstrap, demo-setup, calculator-inputs."""
    if not ctx.resilient_parsing:
        if ctx.invoked_subcommand is not None:
            click.echo(get_snowfort_splash())
        if ctx.obj:
            _get_telemetry(ctx.obj).handshake()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.option("--reset", is_flag=True, help="Ignore existing env and prompt for all values from scratch.")
@click.pass_context
def login(ctx, reset: bool):
    """Prompt for account, user, role, authenticator and print export commands.

    You must run login as an argument to eval so the export lines are applied to
    your current shell; otherwise the variables are only printed and not set:

      eval \"$(snowfort login)\"

    Auth: mfa (password+MFA), keypair (JWT), pat (token as password),
    browser (SSO via external browser)."""
    container = ctx.obj
    config = container.get("ConfigurationProtocol")
    piped = not sys.stdout.isatty()
    stderr_console = Console(stderr=True)

    if reset:
        account = user = role = authenticator_display = ""
        private_key_path = ""
    else:
        account = (config.get_env("SNOWFLAKE_ACCOUNT") or "").strip()
        user = (config.get_env("SNOWFLAKE_USER") or "").strip()
        role = (config.get_env("SNOWFLAKE_ROLE") or "").strip()
        raw_auth = (config.get_env("SNOWFLAKE_AUTHENTICATOR") or "").strip()
        authenticator_display = AUTH_SNOWFLAKE_TO_DISPLAY.get(raw_auth, raw_auth or "mfa")
        private_key_path = (config.get_env("SNOWFLAKE_PRIVATE_KEY_PATH") or "").strip()

    if not reset and (account or user or role or authenticator_display):
        parts = [f"account={account}", f"user={user}", f"role={role}", f"auth={authenticator_display}"]
        parts = [p for p in parts if "=" in p and p.split("=", 1)[1]]
        if parts:
            stderr_console.print("[dim]Current: " + ", ".join(parts) + "[/dim]")

    def ask_fn(p: str, d: str) -> str:
        return _ask(p, d, piped)

    account = ask_fn("Snowflake Account (e.g. org-account or URL)", account or "")
    user = ask_fn("User", user or "")
    role = ask_fn("Role", role or "AUDITOR")
    authenticator_display = ask_fn(
        "Authenticator (mfa, keypair, pat, browser)",
        authenticator_display or "mfa",
    )
    authenticator = AUTH_DISPLAY_TO_SNOWFLAKE.get(
        authenticator_display.strip().lower(),
        authenticator_display.strip() or "externalbrowser",
    )
    if authenticator not in AUTH_DISPLAY_TO_SNOWFLAKE.values():
        authenticator = "username_password_mfa"

    if authenticator == "snowflake_jwt":
        private_key_path = ask_fn("Private key path (PEM file)", private_key_path or "")

    lines = _login_export_lines(account, user, role, authenticator, private_key_path or "")
    print('To set variables in this shell, run: eval "$(snowfort login)"', file=sys.stderr)
    print("\n".join(lines))


@audit.command(name="calculator-inputs")
@click.pass_context
def calculator_inputs(ctx):
    """Generate JSON inputs for Snowflake Pricing Calculator."""
    container = ctx.obj
    telemetry = container.get("TelemetryPort")
    connection_error_type = container.get("ConnectionErrorType")
    try:
        options = get_connection_options(container, interactive=False)
        gateway_factory = container.get("SnowflakeGatewayFactory")
        gateway = gateway_factory(options)
        cursor = gateway.get_cursor()
        calc_class = container.get("CalculatorInterrogatorClass")
        calc = calc_class(cursor)
        inputs = calc.get_inputs()
        print(json.dumps(inputs, indent=2))
    except (connection_error_type, RuntimeError) as e:
        telemetry.error(f"Error: {e}")
        sys.exit(1)


@audit.command()
@click.argument("rule_id", required=False)
@click.pass_context
def rules(ctx, rule_id: str | None):
    """List all registered WAF rules, or show detailed info for one rule by ID (e.g. COST_001, SEC_002)."""
    container = ctx.obj
    try:
        rule_list = container.get_rules()
    except (ValueError, Exception):
        get_all_rules_fn = container.get("get_all_rules")
        rule_list = get_all_rules_fn(container.get("FinancialEvaluator"), container.get("TelemetryPort"), Path.cwd())
    console = Console()
    if rule_id:
        rule_id_upper = rule_id.upper().strip()
        match = next((r for r in rule_list if r.id.upper() == rule_id_upper), None)
        if not match:
            console.print(f"[red]No rule found for: {rule_id}[/red]")
            console.print("Run [bold]snowfort audit rules[/bold] to list all rule IDs.")
            raise SystemExit(1)
        r = match
        table = Table(title=f"Rule: {r.id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("ID", r.id)
        table.add_row("Name", r.name)
        table.add_row("Severity", r.severity.value)
        table.add_row("Pillar", r.pillar)
        table.add_row("Rationale", r.rationale or "(none)")
        table.add_row("Remediation", r.remediation or "(none)")
        console.print(table)
        if r.remediation_key:
            console.print(f"\nRemediation key: [dim]{r.remediation_key}[/dim]")
        console.print("\n[dim]Severity and grading: docs/SEVERITY_AND_GRADING.md[/dim]")
        try:
            load_conventions_fn = container.get("load_conventions")
            conv = load_conventions_fn(Path.cwd())
            conv_lines = conventions_for_pillar(r.pillar, conv)
            if conv_lines:
                console.print("\n[bold]Snowfort conventions[/bold] (relevant to this pillar):")
                conv_table = Table(show_header=True, header_style="cyan")
                conv_table.add_column("Convention", style="cyan")
                conv_table.add_column("Default", style="white")
                for key, val in conv_lines:
                    conv_table.add_row(key, val)
                console.print(conv_table)
                console.print("[dim]Override in pyproject.toml: [tool.snowfort.conventions.warehouse] etc.[/dim]")
        except Exception:
            pass
    else:
        table = Table(title="Registered WAF rules")
        table.add_column("Rule ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Severity", style="yellow")
        table.add_column("Pillar", style="green")
        for r in sorted(rule_list, key=lambda x: (x.pillar, x.id)):
            table.add_row(r.id, r.name, r.severity.value, r.pillar)
        console.print(table)
        console.print("\nFor details: [bold]snowfort audit rules <RULE_ID>[/bold] (e.g. snowfort audit rules COST_001)")
        console.print("[dim]Severity and grading: docs/SEVERITY_AND_GRADING.md[/dim]")


# Import submodules after `audit` is defined so they can register their commands.
from . import bootstrap  # noqa: E402, F401, I001
from . import scan  # noqa: E402, F401, I001
from . import show  # noqa: E402, F401, I001

if __name__ == "__main__":
    main()
