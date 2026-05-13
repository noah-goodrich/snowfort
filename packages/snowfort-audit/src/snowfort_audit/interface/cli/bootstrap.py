"""Bootstrap and demo-setup commands."""

import click

from snowfort_audit.domain.models import BootstrapRequestDTO
from snowfort_audit.interface.cli import (
    _connection_error_hint,
    _warn_externalbrowser_headless,
    audit,
    get_connection_options,
)
from snowfort_audit.interface.timer import timed_operation


@audit.command()
@click.option("--role", default="ACCOUNTADMIN", help="Role to use for bootstrapping (needs Create Role privs)")
@click.option(
    "--keypair",
    is_flag=True,
    default=False,
    help=(
        "Generate an RSA-2048 keypair for Snowflake key-pair authentication. "
        "Writes the private key to --key-path (default: ~/.snowflake/snowfort_rsa_key.p8) "
        "and prints the ALTER USER SQL you must run to register the public key."
    ),
)
@click.option(
    "--key-path",
    default="~/.snowflake/snowfort_rsa_key.p8",
    show_default=True,
    help="Path where the private key PEM file will be written (ignored unless --keypair is set).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="With --keypair: print the ALTER USER SQL without generating or writing anything.",
)
@click.option(
    "--snowflake-user",
    default="",
    help="Snowflake username for the ALTER USER statement (defaults to $SNOWFLAKE_USER or current login).",
)
@click.pass_context
def bootstrap(ctx, role, keypair, key_path, dry_run, snowflake_user):
    """Interactive setup for Audit permissions.

    With --keypair: generate RSA keypair for Snowflake key-pair auth.
    Without --keypair: provision the AUDITOR role (requires an active connection).
    """
    container = ctx.obj
    telemetry = container.get("TelemetryPort")

    if keypair:
        _run_keypair_bootstrap(telemetry, key_path, dry_run, snowflake_user)
        return

    telemetry.step("Snowfort Audit Bootstrap: Initializing permissions...")
    connection_error_type = container.get("ConnectionErrorType")
    try:
        with timed_operation("Bootstrap"):
            options = get_connection_options(container, interactive=True, role_override=role)
            _warn_externalbrowser_headless(options, telemetry)
            gateway_factory = container.get("SnowflakeGatewayFactory")
            gateway = gateway_factory(options)

            current_user = gateway.execute("SELECT CURRENT_USER()").fetchone()[0]
            target_warehouse = telemetry.ask("Enter Warehouse name for auditing tasks", default="COMPUTE_WH")

            request = BootstrapRequestDTO(
                admin_role=role,
                auditor_role="AUDITOR",
                target_warehouse=target_warehouse,
                target_user=current_user,
            )

            telemetry.step("Execution Plan:")
            telemetry.step(f"1. CREATE ROLE IF NOT EXISTS {request.auditor_role}")
            telemetry.step(f"2. GRANT ROLE {request.auditor_role} TO USER {request.target_user}")
            telemetry.step(f"3. GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE {request.auditor_role}")
            telemetry.step(f"4. GRANT USAGE ON WAREHOUSE {request.target_warehouse} TO ROLE {request.auditor_role}")

            if not telemetry.confirm("Proceed with changes?"):
                telemetry.step("Aborted.")
                return

            container.register_singleton("SnowflakeQueryProtocol", gateway)
            use_case = container.get("BootstrapUseCase")
            use_case.execute(request)

            telemetry.step("Bootstrap completed successfully!")

    except (connection_error_type, RuntimeError) as e:
        telemetry.error(f"Error during bootstrap: {e}")
        hint = _connection_error_hint(e)
        if hint:
            telemetry.error(f"Hint: {hint}")
        raise click.Abort() from e


def _run_keypair_bootstrap(telemetry, key_path: str, dry_run: bool, snowflake_user: str) -> None:
    """Generate RSA-2048 keypair and print the ALTER USER SQL."""
    import os

    from snowfort_audit.use_cases.bootstrap import KeypairBootstrapUseCase

    username = snowflake_user or os.environ.get("SNOWFLAKE_USER") or os.environ.get("SNOWFLAKE_USERNAME") or ""
    if not username:
        username = click.prompt("Snowflake username (for ALTER USER SQL)")

    if dry_run:
        telemetry.step("[dry-run] Generating keypair in memory — no files will be written.")
    else:
        telemetry.step(f"Generating RSA-2048 keypair → {key_path}")

    try:
        alter_sql = KeypairBootstrapUseCase().execute(key_path, username=username, dry_run=dry_run)
    except ValueError as exc:
        telemetry.error(f"Keypair bootstrap failed: {exc}")
        raise click.Abort() from exc
    except ImportError as exc:
        telemetry.error(str(exc))
        raise click.Abort() from exc

    if not dry_run:
        telemetry.step(f"Private key written to: {key_path}  (mode 0600 — owner read/write only)")
        telemetry.step("Set the key path in your environment:")
        click.echo(f"  export SNOWFLAKE_PRIVATE_KEY_PATH={key_path}")
        click.echo("  export SNOWFLAKE_AUTHENTICATOR=snowflake_jwt")
    telemetry.step("Run this SQL in Snowsight or SnowSQL to register the public key:")
    click.echo("")
    click.echo(alter_sql)
    click.echo("")
    if dry_run:
        telemetry.step("[dry-run] No files written. Remove --dry-run to write the private key.")


@audit.command(name="demo-setup")
@click.pass_context
def demo_setup(ctx):
    """Create demo account state with WAF violations for testing online scan. Run: snowfort audit scan"""
    container = ctx.obj
    telemetry = container.get("TelemetryPort")
    telemetry.step("Demo setup: creating WAF violations in account...")
    connection_error_type = container.get("ConnectionErrorType")
    try:
        options = get_connection_options(container, interactive=True, role_override="ACCOUNTADMIN")
        _warn_externalbrowser_headless(options, telemetry)
        gateway_factory = container.get("SnowflakeGatewayFactory")
        gateway = gateway_factory(options)
        gateway.connect()
        try:
            from importlib import resources as _res

            sql_content = (
                _res.files("snowfort_audit").joinpath("resources", "demo_setup.sql").read_text(encoding="utf-8")
            )
        except (FileNotFoundError, TypeError):
            from pathlib import Path

            _pkg = Path(__file__).resolve().parent.parent.parent.parent
            _script = _pkg / "examples" / "setup_online_failures.sql"
            sql_content = _script.read_text(encoding="utf-8") if _script.exists() else ""
        if not sql_content:
            telemetry.error("Demo SQL not found.")
            raise click.Abort()
        for s in (x.strip() for x in sql_content.split(";") if x.strip() and not x.strip().startswith("!")):
            if s:
                gateway.execute(s)
                telemetry.step(f"Executed: {s[:45]}...")
        telemetry.step("Done. Run: snowfort audit scan")
    except (connection_error_type, RuntimeError) as e:
        telemetry.error(f"Demo setup failed: {e}")
        hint = _connection_error_hint(e)
        if hint:
            telemetry.error(f"Hint: {hint}")
        raise click.Abort() from e


@audit.command(name="demo-teardown")
@click.pass_context
def demo_teardown(ctx):
    """Remove demo WAF violation objects created by demo-setup."""
    container = ctx.obj
    telemetry = container.get("TelemetryPort")
    telemetry.step("Demo teardown: removing WAF test objects...")
    connection_error_type = container.get("ConnectionErrorType")
    try:
        options = get_connection_options(container, interactive=True, role_override="ACCOUNTADMIN")
        _warn_externalbrowser_headless(options, telemetry)
        gateway_factory = container.get("SnowflakeGatewayFactory")
        gateway = gateway_factory(options)
        gateway.connect()
        try:
            from importlib import resources as _res

            sql_content = (
                _res.files("snowfort_audit").joinpath("resources", "demo_teardown.sql").read_text(encoding="utf-8")
            )
        except (FileNotFoundError, TypeError):
            sql_content = ""
        if not sql_content:
            telemetry.error("Teardown SQL not found.")
            raise click.Abort()
        for s in (x.strip() for x in sql_content.split(";") if x.strip() and not x.strip().startswith("!")):
            if s:
                gateway.execute(s)
                telemetry.step(f"Executed: {s[:45]}...")
        telemetry.step("Done. Test objects removed.")
    except (connection_error_type, RuntimeError) as e:
        telemetry.error(f"Demo teardown failed: {e}")
        raise click.Abort() from e


@audit.command(name="deploy-dashboard")
@click.option("--role", default="ACCOUNTADMIN", help="Role for deploying (needs CREATE STREAMLIT)")
@click.pass_context
def deploy_dashboard(ctx, role):
    """Deploy the Snowfort WAF Audit dashboard to Streamlit-in-Snowflake.

    Creates SNOWFORT.AUDIT schema if needed, uploads app files to a stage,
    and creates/replaces the Streamlit app object.
    """
    from pathlib import Path

    container = ctx.obj
    telemetry = container.get("TelemetryPort")
    connection_error_type = container.get("ConnectionErrorType")

    try:
        options = get_connection_options(container, interactive=True, role_override=role)
        _warn_externalbrowser_headless(options, telemetry)
        gateway_factory = container.get("SnowflakeGatewayFactory")
        gateway = gateway_factory(options)
        gateway.connect()
        cur = gateway.get_cursor()

        telemetry.step("Ensuring SNOWFORT.AUDIT schema exists...")
        cur.execute("CREATE DATABASE IF NOT EXISTS SNOWFORT")
        cur.execute("CREATE SCHEMA IF NOT EXISTS SNOWFORT.AUDIT")
        cur.execute("CREATE STAGE IF NOT EXISTS SNOWFORT.AUDIT.STREAMLIT_STAGE")

        # Upload streamlit app files
        streamlit_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "streamlit"
        if not streamlit_dir.exists():
            telemetry.error(f"Streamlit app directory not found at {streamlit_dir}")
            raise click.Abort()

        telemetry.step("Uploading Streamlit app files...")
        cur.execute(f"PUT 'file://{streamlit_dir}/snowfort_app.py' @SNOWFORT.AUDIT.STREAMLIT_STAGE/ "
                    "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        cur.execute(f"PUT 'file://{streamlit_dir}/environment.yml' @SNOWFORT.AUDIT.STREAMLIT_STAGE/ "
                    "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

        # Upload pages
        pages_dir = streamlit_dir / "pages"
        for page_file in sorted(pages_dir.glob("*.py")):
            cur.execute(f"PUT 'file://{page_file}' @SNOWFORT.AUDIT.STREAMLIT_STAGE/pages/ "
                        "AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            telemetry.step(f"  Uploaded: pages/{page_file.name}")

        # Create the Streamlit object
        telemetry.step("Creating Streamlit app...")
        cur.execute("""
            CREATE OR REPLACE STREAMLIT SNOWFORT.AUDIT.SNOWFORT_AUDIT_DASHBOARD
                ROOT_LOCATION = '@SNOWFORT.AUDIT.STREAMLIT_STAGE'
                MAIN_FILE = 'snowfort_app.py'
                QUERY_WAREHOUSE = CURRENT_WAREHOUSE()
                COMMENT = 'Snowfort WAF Audit Dashboard — score trends, drill-down, remediation'
        """)

        # Get the URL
        cur.execute("SHOW STREAMLITS LIKE 'SNOWFORT_AUDIT_DASHBOARD' IN SCHEMA SNOWFORT.AUDIT")
        rows = cur.fetchall()
        if rows:
            telemetry.step("Dashboard deployed successfully!")
            telemetry.step("Open in Snowsight: Streamlit > SNOWFORT.AUDIT.SNOWFORT_AUDIT_DASHBOARD")
        else:
            telemetry.step("Dashboard created. Open it from Snowsight > Streamlit.")

    except (connection_error_type, RuntimeError) as e:
        telemetry.error(f"Deploy failed: {e}")
        hint = _connection_error_hint(e)
        if hint:
            telemetry.error(f"Hint: {hint}")
        raise click.Abort() from e
