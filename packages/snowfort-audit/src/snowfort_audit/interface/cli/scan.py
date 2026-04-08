"""Scan command and offline/online scan runners."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from snowfort_audit.domain.results import AuditResult
from snowfort_audit.interface.cli import (
    _connection_error_hint,
    _prompt_account_config,
    audit,
    get_connection_options,
)
from snowfort_audit.interface.cli.report import (
    report_findings,
    report_findings_guided,
    write_audit_cache,
)
from snowfort_audit.interface.timer import timed_operation
from snowfort_audit.interface.tui import run_interactive


def _after_scan_report(
    path: str,
    result: AuditResult,
    target_name: str,
    rule_filter: list | None,
    rules: list,
    cortex: bool,
    gateway,
    violations: list,
    offline: bool,
    manifest: bool,
    container,
    telemetry,
) -> bool:
    """Write cache, optional cortex summary, rule-filter warning. Returns True if caller should sys.exit(1)."""
    try:
        write_audit_cache(Path(path).resolve(), result, target_name)
    except OSError as e:
        telemetry.debug(f"Could not write audit cache: {e}")
    if rule_filter and not rules:
        telemetry.warning("No rules matched the given --rule ID(s). Run 'snowfort audit rules' to list valid IDs.")
    if cortex and gateway and not manifest:
        _run_cortex_summary(container, gateway, violations)
    return bool(violations and offline)


def _run_cortex_summary(container, gateway, violations: list) -> None:
    """Print Cortex executive summary panel if gateway and violations available."""
    connection_error_type = container.get("ConnectionErrorType")
    try:
        cur = gateway.get_cursor()
        SynthesizerClass = container.get("CortexSynthesizerClass")
        syn = SynthesizerClass(cur)
        Console().print(Panel(syn.summarize(violations), title="Executive Summary (Cortex)", border_style="cyan"))
    except (connection_error_type, RuntimeError) as exc:
        telemetry = container.get("TelemetryPort")
        telemetry.error(f"Cortex summary failed: {exc}")


def _fmt_duration(seconds: float) -> str:
    """Format a duration for the profile table."""
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    mins, secs = divmod(seconds, 60)
    return f"{int(mins)}m {secs:.1f}s"


def _print_profile_table(timings: list, console: Console) -> None:
    """Print per-rule timing sorted by duration (slowest first)."""
    if not timings:
        return
    table = Table(title="Rule Profile (slowest first)", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Duration", justify="right", style="yellow")
    sorted_timings = sorted(timings, key=lambda x: x[2], reverse=True)
    for i, (rule_id, rule_name, duration_s) in enumerate(sorted_timings, 1):
        table.add_row(str(i), rule_id, rule_name, _fmt_duration(duration_s))
    console.print(table)


def _run_offline_scan(container, path, rules_dir, rule_ids: list[str] | None = None, profile: bool = False) -> tuple:
    container.register_singleton("CustomRulesDir", rules_dir)
    if rule_ids:
        container.register_singleton("ScanRuleIds", frozenset(r.upper() for r in rule_ids))
    use_case = container.get("OfflineScanUseCase")
    violations = use_case.execute(path, profile=profile)
    rules = container.get_rules()
    timings = use_case.profile_timings if profile else []
    return violations, rules, timings


def _run_online_scan(
    container,
    account,
    user,
    role,
    authenticator,
    rules_dir,
    workers: int = 4,
    include_snowfort_db: bool = False,
    rule_ids: list[str] | None = None,
    profile: bool = False,
) -> tuple:
    if rule_ids:
        container.register_singleton("ScanRuleIds", frozenset(r.upper() for r in rule_ids))
    options = get_connection_options(
        container,
        interactive=True,
        account_override=account,
        user_override=user,
        role_override=role,
        authenticator_override=authenticator,
    )
    gateway_factory = container.get("SnowflakeGatewayFactory")
    gateway = gateway_factory(options)
    container.register_singleton("SnowflakeClient", gateway)
    container.register_singleton("CustomRulesDir", rules_dir)

    telemetry = container.get("TelemetryPort")
    telemetry.step("Running online rules...")
    use_case = container.get("OnlineScanUseCase")
    violations = use_case.execute(workers=workers, include_snowfort_db=include_snowfort_db, profile=profile)
    rules = container.get_rules()
    timings = use_case.profile_timings if profile else []
    return violations, rules, gateway, timings


def _emit_scan_output(
    quiet: bool,
    use_guided: bool,
    result,
    violations,
    rules,
    telemetry,
    manifest: bool,
    target_name: str,
    verbose: bool,
    audit_metadata: dict,
) -> None:
    """Print scan result: quiet one-liner, guided report, or flat report."""
    if quiet:
        sc = result.scorecard
        print(f"Score: {sc.compliance_score}/100 ({sc.grade}) — {sc.total_violations} violation(s)")
        return
    if use_guided:
        report_findings_guided(violations, rules, telemetry, manifest, target_name, audit_metadata, result=result)
    else:
        report_findings(violations, rules, telemetry, manifest, target_name, verbose, audit_metadata, result=result)


def _log_scan_preamble(telemetry, quiet: bool, path: str, rule_ids: tuple, cortex: bool, offline: bool) -> bool:
    """Emit pre-scan telemetry messages and resolve cortex flag."""
    if not quiet:
        telemetry.step(f"Snowfort Audit Scan (Target: {path})")
    if rule_ids and not quiet:
        rule_list = ", ".join(sorted(r.upper() for r in rule_ids))
        telemetry.step(f"Rule filter: running only {len(rule_ids)} rule(s): {rule_list}")
    if cortex and offline:
        if not quiet:
            telemetry.step("--cortex requires online mode; skipping AI summary.")
        return False
    if cortex and not quiet:
        telemetry.step("AI Augmentation enabled.")
    return cortex


@audit.command(name="scan")
@click.option("--offline", is_flag=True, help="Run only offline code content checks (Static Analysis)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose violation output (remediation column)")
@click.option(
    "--log-level",
    "log_level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Log level: DEBUG/INFO/WARNING/ERROR. Also SNOWFORT_LOG_LEVEL.",
)
@click.option(
    "--workers",
    type=int,
    default=4,
    help="Parallel workers for account-level rules (1=sequential). Default: 4.",
)
@click.option(
    "--include-snowfort-db",
    "include_snowfort_db",
    is_flag=True,
    help="Include SNOWFORT database in view-phase checks (auditing Snowfort itself).",
)
@click.option("--cortex", is_flag=True, help="Use AI to synthesize findings (requires Cortex)")
@click.option(
    "--guided",
    "scan_mode",
    flag_value="guided",
    help="Concept-grouped output with rationale and remediation (default when TTY).",
)
@click.option(
    "--auto",
    "scan_mode",
    flag_value="auto",
    help="Flat violations table (default when piped/CI).",
)
@click.option("--account", help="Snowflake account identifier")
@click.option("--user", help="Snowflake username")
@click.option("--role", help="Snowflake role")
@click.option("--authenticator", help="Snowflake authenticator")
@click.option("--manifest", is_flag=True, help="Output machine-readable JSON manifest")
@click.option(
    "--rule",
    "rule_ids",
    multiple=True,
    help="Run only these rule(s) (e.g. --rule PERF_005). Omit to run all rules.",
)
@click.option("--rules-dir", default="./custom_rules", help="Directory containing custom audit rules")
@click.option(
    "--path",
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project path for offline scan.",
)
@click.option(
    "--billing-model",
    type=click.Choice(["on_demand", "reserved"], case_sensitive=False),
    default=None,
    help="Billing model for cost context (On-Demand vs Reserved Capacity); influences cost recommendations.",
)
@click.option("--quiet", "-q", is_flag=True, help="Minimal output: score and violation count only.")
@click.option("--profile", is_flag=True, help="Print per-rule execution time sorted by duration after scan.")
@click.option(
    "--no-tui",
    "no_tui",
    is_flag=True,
    help="Do not launch the interactive TUI after the scan (default: launch TUI when running in a terminal).",
)
@click.pass_context
def scan(
    ctx,
    offline: bool,
    verbose: bool,  # noqa: ARG001
    log_level: str,
    quiet: bool,
    profile: bool,
    no_tui: bool,
    workers: int,
    include_snowfort_db: bool,
    cortex: bool,
    scan_mode: str | None,
    account: str | None,
    user: str | None,
    role: str | None,
    authenticator: str | None,
    manifest: bool,
    rule_ids: tuple[str, ...],
    rules_dir: str,
    path: str,
    billing_model: str | None,
):
    """Run the snowfort-audit WAF Scorecard. Launches the interactive TUI by default when run in a terminal; use --no-tui for report-only output."""
    project_root = Path(path).resolve()
    container = ctx.obj
    prompt_fn = _prompt_account_config if sys.stdout.isatty() else None
    ensure_account_config_fn = container.get("ensure_account_config")
    ensure_account_config_fn(project_root, prompt_fn=prompt_fn)

    telemetry = container.get("TelemetryPort")
    connection_error_type = container.get("ConnectionErrorType")
    telemetry.set_log_level("WARNING" if quiet else log_level)
    cortex = _log_scan_preamble(telemetry, quiet, path, rule_ids, cortex, offline)

    violations = []
    rules = []
    gateway = None
    profile_timings = []
    try:
        with timed_operation("Scan"):
            rule_filter = list(rule_ids) if rule_ids else None
            if offline:
                violations, rules, profile_timings = _run_offline_scan(
                    container, path, rules_dir, rule_ids=rule_filter, profile=profile
                )
                target_name = path
                account_id = ""
            else:
                violations, rules, gateway, profile_timings = _run_online_scan(
                    container,
                    account,
                    user,
                    role,
                    authenticator,
                    rules_dir,
                    workers,
                    include_snowfort_db,
                    rule_ids=rule_filter,
                    profile=profile,
                )
                target_name = "Snowflake account"
                try:
                    account_id = (gateway.execute("SELECT CURRENT_ACCOUNT()").fetchone() or (None,))[0] or ""
                except Exception:
                    account_id = ""

            use_guided = scan_mode == "guided" or (scan_mode is None and sys.stdout.isatty())
            audit_metadata = {"billing_model": billing_model} if billing_model else {}
            audit_metadata["account_id"] = account_id
            result = AuditResult.from_violations(violations, metadata=audit_metadata)
            _emit_scan_output(
                quiet,
                use_guided,
                result,
                violations,
                rules,
                telemetry,
                manifest,
                target_name,
                verbose,
                audit_metadata,
            )

            if profile and profile_timings:
                _print_profile_table(profile_timings, Console(stderr=True))

            if _after_scan_report(
                path,
                result,
                target_name,
                rule_filter,
                rules,
                cortex,
                gateway,
                violations,
                offline,
                manifest,
                container,
                telemetry,
            ):
                sys.exit(1)

            # Default: launch interactive TUI when in a terminal (unless --no-tui or --quiet)
            if not quiet and not no_tui and sys.stdout.isatty():
                run_interactive(
                    result,
                    rules,
                    violations,
                    container=container,
                    project_root=project_root,
                )

    except (connection_error_type, OSError, RuntimeError) as e:
        telemetry.error(f"Scan failed: {e}")
        hint = _connection_error_hint(e)
        if hint:
            telemetry.error(f"Hint: {hint}")
        raise click.Abort() from e
