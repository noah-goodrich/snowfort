"""Show command: view/export audit results from cache or re-scan."""

import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console

from snowfort_audit.domain.results import AuditResult, AuditScorecard
from snowfort_audit.domain.rule_definitions import Severity, Violation, pillar_from_rule_id
from snowfort_audit.interface.cli import (
    _prompt_account_config,
    audit,
    get_connection_options,
)
from snowfort_audit.interface.cli.report import (
    build_yaml_report,
    report_findings_guided,
    report_pillar_detail,
    report_rule_detail,
    show_filtered_table,
    write_audit_cache,
)
from snowfort_audit.interface.cli.scan import _run_offline_scan, _run_online_scan
from snowfort_audit.interface.timer import timed_operation


def _load_cached_data(cache_file: Path) -> dict:
    with open(cache_file, encoding="utf-8") as f:
        return json.load(f)


def _parse_cached_result(data: dict, project_root: Path, container) -> tuple[AuditResult, list, str, str]:
    vl = []
    for v in data.get("violations", []):
        s = (v.get("severity") or "LOW").upper()
        try:
            sev = Severity(s)
        except ValueError:
            sev = Severity.LOW
        vl.append(
            Violation(
                v.get("rule_id", ""),
                v.get("resource_name", ""),
                v.get("message", ""),
                sev,
                (v.get("pillar") or "").strip(),
                v.get("remediation_key"),
                v.get("remediation_instruction"),
            )
        )
    sc = data.get("scorecard", {})
    card = AuditScorecard(
        compliance_score=int(sc.get("compliance_score", 100)),
        total_violations=int(sc.get("total_violations", 0)),
        critical_count=int(sc.get("critical_count", 0)),
        high_count=int(sc.get("high_count", 0)),
        medium_count=int(sc.get("medium_count", 0)),
        low_count=int(sc.get("low_count", 0)),
        pillar_scores=dict(sc.get("pillar_scores", {})),
        pillar_grades=dict(sc.get("pillar_grades", {})),
    )
    result = AuditResult(violations=vl, scorecard=card, metadata=data.get("metadata", {}))
    get_all_rules_fn = container.get("get_all_rules")
    rules = get_all_rules_fn(container.get("FinancialEvaluator"), container.get("TelemetryPort"), project_root)
    target_name = data.get("target_name", ".")
    timestamp = data.get("timestamp_utc", "")
    return result, rules, target_name, timestamp


def _do_rescan(
    container,
    project_root: Path,
    path: str,
    rules_dir: str,
    offline: bool,
    account: str | None,
    user: str | None,
    role: str | None,
    authenticator: str | None,
) -> tuple[AuditResult, list, str, str]:
    telemetry = container.get("TelemetryPort")
    telemetry.step("Re-scanning (--re-scan)...")
    if not offline:
        prompt_fn = _prompt_account_config if sys.stdout.isatty() else None
        ensure_account_config_fn = container.get("ensure_account_config")
        ensure_account_config_fn(project_root, prompt_fn=prompt_fn)
    if offline:
        violations, rules = _run_offline_scan(container, path, rules_dir)
        target_name = path
        audit_metadata = {"account_id": ""}
    else:
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
        violations, rules, gateway = _run_online_scan(
            container, account, user, role, authenticator, rules_dir, 1, False
        )
        target_name = "Snowflake account"
        try:
            account_id = (gateway.execute("SELECT CURRENT_ACCOUNT()").fetchone() or (None,))[0] or ""
        except Exception:
            account_id = ""
        audit_metadata = {"account_id": account_id}
    result = AuditResult.from_violations(violations, metadata=audit_metadata)
    try:
        write_audit_cache(project_root, result, target_name)
    except OSError as e:
        telemetry.debug(f"Could not write audit cache: {e}")
    return result, rules, target_name, ""


def _export_yaml_report(
    result: AuditResult,
    rules: list,
    project_root: Path,
    output_path: str,
    load_account_config_fn=None,
) -> None:
    report_data = build_yaml_report(result, rules, project_root, load_account_config_fn=load_account_config_fn)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    yaml_str = yaml.dump(report_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    out.write_text(yaml_str, encoding="utf-8")
    Console().print(f"[green]Report written to {output_path}[/green]")


def _apply_show_filters(
    violations: list,
    pillar_filter: str | None,
    rule_id_filter: str | None,
    severity_filter: str | None,
    resource_filter: str | None,
) -> list:
    filtered = []
    for v in violations:
        p = (v.pillar or pillar_from_rule_id(v.rule_id) or "").strip()
        if pillar_filter and p.upper() != pillar_filter.upper():
            continue
        if rule_id_filter and v.rule_id.upper() != rule_id_filter.upper().strip():
            continue
        if severity_filter and v.severity.value.upper() != severity_filter.upper():
            continue
        if resource_filter and resource_filter.lower() not in (v.resource_name or "").lower():
            continue
        filtered.append(v)
    return filtered


def _route_show_output(
    result: AuditResult,
    rules: list,
    target_name: str,
    timestamp: str,
    filtered_vl: list,
    pillar_filter: str | None,
    rule_id_filter: str | None,
    severity_filter: str | None,
    resource_filter: str | None,
    count_only: bool,
    interactive: bool,
    container,
    project_root: Path,
) -> None:
    if count_only:
        Console().print(str(len(filtered_vl)))
        return
    if rule_id_filter and not severity_filter and not resource_filter:
        report_rule_detail(filtered_vl, rules, rule_id_filter)
        return
    if pillar_filter and not rule_id_filter and not severity_filter and not resource_filter:
        report_pillar_detail(result.violations, rules, pillar_filter)
        return
    if pillar_filter or rule_id_filter or severity_filter or resource_filter:
        show_filtered_table(filtered_vl, target_name, timestamp)
        return
    if interactive:
        from snowfort_audit.interface.tui import run_interactive

        run_interactive(result, rules, result.violations, container=container, project_root=project_root)
        return
    report_findings_guided(
        result.violations,
        rules,
        container.get("TelemetryPort"),
        False,
        target_name=target_name,
        result=result,
    )


@audit.command(name="show")
@click.option(
    "--path",
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project path (cache: .snowfort/audit_results.json)",
)
@click.option("--pillar", "pillar_filter", default=None, help="Filter/drill by pillar (e.g. Security, Cost)")
@click.option("--rule-id", "rule_id_filter", default=None, help="Filter or drill by rule ID (e.g. COST_001)")
@click.option(
    "--severity",
    "severity_filter",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"], case_sensitive=False),
    help="Filter by severity",
)
@click.option("--resource", "resource_filter", default=None, help="Filter by resource name (substring)")
@click.option("--count-only", is_flag=True, help="Print only the count of matching violations")
@click.option("--interactive", is_flag=True, help="Launch interactive TUI to navigate cached results with keyboard")
@click.option(
    "--output",
    "-o",
    "output_path",
    default=None,
    type=click.Path(),
    help="Export YAML report to file (from cache).",
)
@click.option(
    "--re-scan",
    "re_scan",
    is_flag=True,
    help="Run a fresh scan before showing/exporting (use with -o for one-command YAML).",
)
@click.option("--offline", is_flag=True, help="With --re-scan: run offline scan only")
@click.option("--account", help="With --re-scan (online): Snowflake account")
@click.option("--user", help="With --re-scan (online): Snowflake user")
@click.option("--role", help="With --re-scan (online): Snowflake role")
@click.option("--authenticator", help="With --re-scan (online): Snowflake authenticator")
@click.option("--rules-dir", default="./custom_rules", help="With --re-scan: custom rules directory")
@click.pass_context
def show_cmd(
    ctx,
    path: str,
    pillar_filter: str | None,
    rule_id_filter: str | None,
    severity_filter: str | None,
    resource_filter: str | None,
    count_only: bool,
    interactive: bool,
    output_path: str | None,
    re_scan: bool,
    offline: bool,
    account: str | None,
    user: str | None,
    role: str | None,
    authenticator: str | None,
    rules_dir: str,
):
    """View or export audit results (from cache or after a fresh scan with --re-scan)."""
    container = ctx.obj
    project_root = Path(path).resolve()
    cache_file = project_root / ".snowfort" / "audit_results.json"

    if re_scan:
        with timed_operation("Show (re-scan)"):
            result, rules, target_name, timestamp = _do_rescan(
                container,
                project_root,
                path,
                rules_dir,
                offline,
                account,
                user,
                role,
                authenticator,
            )
        if output_path:
            with timed_operation("Export YAML"):
                _export_yaml_report(
                    result,
                    rules,
                    project_root,
                    output_path,
                    load_account_config_fn=container.get("load_account_config"),
                )
            return
        timestamp = ""
    else:
        if not cache_file.is_file():
            Console().print(
                "[yellow]No cached audit results. Run snowfort audit scan first (or use --re-scan).[/yellow]"
            )
            raise SystemExit(1)
        data = _load_cached_data(cache_file)
        result, rules, target_name, timestamp = _parse_cached_result(data, project_root, container)

    if output_path:
        with timed_operation("Export YAML"):
            _export_yaml_report(
                result,
                rules,
                project_root,
                output_path,
                load_account_config_fn=container.get("load_account_config"),
            )
        return

    has_filter = pillar_filter or rule_id_filter or severity_filter or resource_filter
    if has_filter or count_only:
        filtered_vl = _apply_show_filters(
            result.violations, pillar_filter, rule_id_filter, severity_filter, resource_filter
        )
        _route_show_output(
            result,
            rules,
            target_name,
            timestamp,
            filtered_vl,
            pillar_filter,
            rule_id_filter,
            severity_filter,
            resource_filter,
            count_only,
            interactive,
            container,
            project_root,
        )
        return

    _route_show_output(
        result,
        rules,
        target_name,
        timestamp,
        result.violations,
        pillar_filter,
        rule_id_filter,
        severity_filter,
        resource_filter,
        count_only,
        interactive,
        container,
        project_root,
    )
