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
@click.pass_context
def bootstrap(ctx, role):
    """Interactive setup for Audit permissions."""
    container = ctx.obj
    telemetry = container.get("TelemetryPort")

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
