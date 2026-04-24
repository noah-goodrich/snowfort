"""Report rendering and formatting for audit CLI (scorecard, findings, YAML export)."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from snowfort_audit.domain.account_config import (
    ACCOUNT_TOPOLOGY_MULTI_ENV,
    DEFAULT_ENVIRONMENTS,
)
from snowfort_audit.domain.conventions import SnowfortConventions
from snowfort_audit.domain.guided import group_violations_by_concept
from snowfort_audit.domain.results import AuditResult, AuditScorecard
from snowfort_audit.domain.rule_definitions import (
    PILLAR_COLORS,
    PILLAR_DISPLAY_ORDER,
    Severity,
    Violation,
    pillar_from_rule_id,
)


def severity_border_style(severity: Severity) -> str:
    if severity in (Severity.CRITICAL, Severity.HIGH):
        return "red"
    if severity in (Severity.MEDIUM, Severity.LOW):
        return "yellow"
    return "dim"


def pillar_style(pillar: str) -> str:
    color = PILLAR_COLORS.get(pillar, "dim")
    return f"[{color}]{pillar}[/{color}]"


def _grade_status(grade: str) -> str:
    if grade == "A":
        return "[green]Healthy[/green]"
    if grade in ("B", "C"):
        return "[yellow]Review[/yellow]"
    return "[red]Critical[/red]"


def conventions_for_pillar(pillar: str, conv: SnowfortConventions) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    p = (pillar or "").strip().upper()
    if p in ("COST", "PERFORMANCE", "RELIABILITY"):
        w = conv.warehouse
        lines.append(("warehouse.auto_suspend_seconds", str(w.auto_suspend_seconds)))
        lines.append(("warehouse.max_statement_timeout_seconds", str(w.max_statement_timeout_seconds)))
        lines.append(("warehouse.scaling_policy_mcw", w.scaling_policy_mcw))
    if p == "SECURITY":
        s = conv.security
        lines.append(("security.require_mfa_all_users", str(s.require_mfa_all_users)))
        lines.append(("security.require_network_policy", str(s.require_network_policy)))
        lines.append(("security.min_account_admins", str(s.min_account_admins)))
        lines.append(("security.max_account_admins", str(s.max_account_admins)))
    if p in ("GOVERNANCE", "OPERATIONS"):
        t = conv.tags
        lines.append(("tags.required_tags", ", ".join(t.required_tags)))
        lines.append(("tags.iac_tags", ", ".join(t.iac_tags)))
    if p == "OPERATIONS" and not any(k.startswith("warehouse.") for k, _ in lines):
        w = conv.warehouse
        lines.append(("warehouse.auto_suspend_seconds", str(w.auto_suspend_seconds)))
        lines.append(("warehouse.max_statement_timeout_seconds", str(w.max_statement_timeout_seconds)))
    return lines


def _enrichment_fields(v: Violation, rule: Any | None) -> dict:
    """Cortex-consumable enrichment fields shared by cache, manifest, and YAML serializers.

    blast_radius is None for Account-level findings (broad applicability, not per-object).
    """
    return {
        "category": v.category.value,
        "context": (rule.rationale or "") if rule is not None else "",
        "blast_radius": None if str(v.resource_name).strip().upper() == "ACCOUNT" else 1,
        "quick_win": bool(v.remediation_key),
        "remediation_key": v.remediation_key,
    }


def _violation_enriched(v: Violation, rule: Any | None) -> dict:
    """Full violation dict for JSON cache and manifest output."""
    d = asdict(v)
    d["severity"] = v.severity.value
    d.update(_enrichment_fields(v, rule))
    return d


def write_audit_cache(
    project_root: Path,
    result: AuditResult,
    target_name: str,
    rules: list[Any] | None = None,
) -> None:
    cache_dir = project_root / ".snowfort"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "audit_results.json"

    rules_by_id = {r.id: r for r in (rules or [])}
    sc = result.scorecard
    payload = {
        "target_name": target_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": result.metadata,
        "scorecard": {
            "compliance_score": sc.compliance_score,
            "grade": sc.grade,
            "adjusted_score": sc.adjusted_score,
            "adjusted_grade": sc.adjusted_grade,
            "actionable_count": sc.actionable_count,
            "expected_count": sc.expected_count,
            "informational_count": sc.informational_count,
            "total_violations": sc.total_violations,
            "critical_count": sc.critical_count,
            "high_count": sc.high_count,
            "medium_count": sc.medium_count,
            "low_count": sc.low_count,
            "pillar_scores": sc.pillar_scores,
            "pillar_grades": sc.pillar_grades,
        },
        "violations": [_violation_enriched(v, rules_by_id.get(v.rule_id)) for v in result.violations],
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _render_manifest_json(
    violations: list,
    telemetry,
    audit_metadata: dict | None,
    rules: list[Any] | None = None,
) -> None:
    telemetry.step("Generating JSON Manifest...")
    meta = audit_metadata or {}
    rules_by_id = {r.id: r for r in (rules or [])}
    enriched = [_violation_enriched(v, rules_by_id.get(v.rule_id)) for v in violations]
    if meta:
        print(json.dumps({"violations": enriched, "metadata": meta}, indent=2, default=str))
    else:
        print(json.dumps(enriched, indent=2, default=str))


def _render_scorecard_flat(console: Console, result: AuditResult, target_name: str) -> None:
    scorecard = result.scorecard
    header = f"Snowflake Well-Architected Scorecard for [cyan]{target_name}[/cyan]"
    score_text = f"Score: [bold]{scorecard.compliance_score}/100[/bold] ([bold]{scorecard.grade}[/bold])"
    if result.metadata.get("billing_model"):
        bm = result.metadata["billing_model"].replace("_", " ").title()
        score_text += f"  |  Billing: [dim]{bm}[/dim]"
    console.print(Panel(score_text, title=header, border_style="cyan"))


def _render_pillar_table_flat(console: Console, scorecard: AuditScorecard) -> None:
    if not scorecard.pillar_scores:
        return
    pillar_table = Table(title="Pillar Breakdown", show_header=True, header_style="cyan")
    pillar_table.add_column("Pillar", style="cyan")
    pillar_table.add_column("Score", justify="right")
    pillar_table.add_column("Grade", justify="center")
    pillar_table.add_column("Status", justify="center")
    for p in PILLAR_DISPLAY_ORDER:
        if p not in scorecard.pillar_scores:
            continue
        score = scorecard.pillar_scores[p]
        grade = scorecard.pillar_grades.get(p, "-")
        pillar_table.add_row(pillar_style(p), f"{int(score)}", grade, _grade_status(grade))
    console.print(pillar_table)


def _violation_sort_key(v: Violation):
    sr = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    po = {p: i for i, p in enumerate(PILLAR_DISPLAY_ORDER)}
    pillar = v.pillar or pillar_from_rule_id(v.rule_id)
    return (sr.get(v.severity, 4), po.get(pillar, 99), v.rule_id)


def _render_violations_table_flat(console: Console, violations: list, verbose: bool) -> None:
    violations_sorted = sorted(violations, key=_violation_sort_key)
    console.print(f"\n[bold]Violations ({len(violations)}):[/bold]")
    viol_table = Table(show_header=True, header_style="cyan")
    viol_table.add_column("Severity", style="bold", width=10)
    viol_table.add_column("Pillar", width=10)
    viol_table.add_column("Rule", width=12)
    viol_table.add_column("Resource", width=24)
    viol_table.add_column("Message")
    if verbose:
        viol_table.add_column("Remediation")
    for v in violations_sorted:
        if v.severity in (Severity.CRITICAL, Severity.HIGH):
            sev_style = "[red]"
        elif v.severity in (Severity.MEDIUM, Severity.LOW):
            sev_style = "[yellow]"
        else:
            sev_style = "[white]"
        pillar = v.pillar or pillar_from_rule_id(v.rule_id)
        rem = (v.remediation_instruction or "-") if verbose else None
        row = [f"{sev_style}{v.severity.value}[/]", pillar_style(pillar), v.rule_id, v.resource_name, v.message]
        if verbose:
            row.append(rem or "-")
        viol_table.add_row(*row)
    console.print(viol_table)


def report_findings(
    violations,
    _rules,
    telemetry,
    manifest,
    target_name: str = ".",
    verbose: bool = False,
    audit_metadata: dict | None = None,
    result: AuditResult | None = None,
    errored_count: int = 0,
) -> None:
    if manifest:
        _render_manifest_json(violations, telemetry, audit_metadata, rules=_rules)
        return
    console = Console()
    result = result or AuditResult.from_violations(violations, metadata=audit_metadata or {})
    _render_scorecard_flat(console, result, target_name)
    _render_pillar_table_flat(console, result.scorecard)
    if errored_count:
        console.print(f"[bold red]Warning: {errored_count} rule(s) errored — results may be incomplete.[/bold red]")
    if not violations:
        console.print("[green]Perfect Score: No WAF violations detected.[/green]")
        return
    _render_violations_table_flat(console, violations, verbose)


def _render_scorecard_guided(console: Console, result: AuditResult, target_name: str) -> None:
    scorecard = result.scorecard
    header = f"Snowflake Well-Architected Scorecard for [cyan]{target_name}[/cyan]"
    sc_val = scorecard.compliance_score
    bar_color = "green" if sc_val >= 90 else ("yellow" if sc_val >= 70 else "red")
    filled = round(sc_val / 100 * 30)
    bar = f"[{bar_color}]{'━' * filled}[/{bar_color}][dim]{'━' * (30 - filled)}[/dim]"
    score_text = f"Score: [bold]{sc_val}/100[/bold] ({scorecard.grade})  {bar}"
    if result.metadata.get("billing_model"):
        bm = result.metadata["billing_model"].replace("_", " ").title()
        score_text += f"  |  Billing: [dim]{bm}[/dim]"
    console.print(Panel(score_text, title=header, border_style="cyan"))


def _render_pillar_table_guided(console: Console, scorecard: AuditScorecard) -> None:
    if not scorecard.pillar_scores:
        return
    pillar_table = Table(title="Pillar Breakdown", show_header=True, header_style="cyan")
    pillar_table.add_column("Pillar", style="cyan")
    pillar_table.add_column("Score", justify="right")
    pillar_table.add_column("", width=12)
    pillar_table.add_column("Grade", justify="center")
    pillar_table.add_column("Status", justify="center")
    for p in PILLAR_DISPLAY_ORDER:
        if p not in scorecard.pillar_scores:
            continue
        score = scorecard.pillar_scores[p]
        grade = scorecard.pillar_grades.get(p, "-")
        pc = "green" if score >= 90 else ("yellow" if score >= 70 else "red")
        pf = round(score / 100 * 10)
        pbar = f"[{pc}]{'━' * pf}[/{pc}][dim]{'━' * (10 - pf)}[/dim]"
        pillar_table.add_row(pillar_style(p), f"{int(score)}", pbar, grade, _grade_status(grade))
    console.print(pillar_table)


def _render_pillar_checklists(
    console: Console,
    violations: list,
    rules: list,
    scorecard: AuditScorecard,
) -> None:
    violations_by_rule: dict[str, list] = {}
    for v in violations:
        violations_by_rule.setdefault(v.rule_id, []).append(v)
    rules_by_pillar: dict[str, list] = {}
    for r in rules:
        p = r.pillar or pillar_from_rule_id(r.id)
        if p not in PILLAR_DISPLAY_ORDER:
            p = "Other"
        rules_by_pillar.setdefault(p, []).append(r)

    for p in PILLAR_DISPLAY_ORDER:
        p_rules = sorted(rules_by_pillar.get(p, []), key=lambda x: x.id)
        failed_rules = [r for r in p_rules if r.id in violations_by_rule]
        passed_count = len(p_rules) - len(failed_rules)
        p_score = scorecard.pillar_scores.get(p, 100)
        p_grade = scorecard.pillar_grades.get(p, "A")
        header_style = "green" if p_grade == "A" else ("yellow" if p_grade in ("B", "C") else "red")
        pillar_header = f"[{header_style} bold]{p}[/{header_style} bold]  [dim]{int(p_score)}/100 ({p_grade})[/dim]"
        console.print(f"\n{pillar_header}")

        if not failed_rules:
            console.print(f"  [green]All {passed_count} checks passed.[/green]")
            continue

        rule_tbl = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1))
        rule_tbl.add_column(width=2)
        rule_tbl.add_column(width=16, style="bold")
        rule_tbl.add_column(ratio=1, no_wrap=True)
        rule_tbl.add_column(width=14, justify="right")
        for r in failed_rules:
            pv = violations_by_rule[r.id]
            sev = pv[0].severity
            if sev == Severity.CRITICAL:
                sev_style, indicator = "[red]", "[red]!![/red]"
            elif sev == Severity.HIGH:
                sev_style, indicator = "[red]", "[red]![/red] "
            else:
                sev_style, indicator = "[yellow]", "[yellow]~[/yellow] "
            finding_label = f"{sev_style}{sev.value}[/] x{len(pv)}" if len(pv) > 1 else f"{sev_style}{sev.value}[/]"
            rule_tbl.add_row(indicator, r.id, r.name, finding_label)
        console.print(rule_tbl)
        if passed_count > 0:
            console.print(f"  [green]+{passed_count} checks passed[/green]")


def _render_top_actions(console: Console, rules: list, violations_by_rule: dict) -> None:
    severity_rank = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    rule_impact: list[tuple[int, int, str, str, str]] = []
    for r in rules:
        pv = violations_by_rule.get(r.id, [])
        if not pv:
            continue
        worst_sev = min(pv, key=lambda v: severity_rank.get(v.severity, 9)).severity
        rule_impact.append((severity_rank[worst_sev], len(pv), r.id, r.name, worst_sev.value))
    rule_impact.sort(key=lambda x: (x[0], -x[1]))
    top_actions = rule_impact[:3]
    if not top_actions:
        return
    console.print("")
    console.print("[bold]Top 3 actions[/bold]")
    for i, (_, cnt, rid, rname, sval) in enumerate(top_actions, 1):
        sc = "[red]" if sval in ("CRITICAL", "HIGH") else "[yellow]"
        console.print(f"  {i}. {sc}{sval}[/] [bold]{rid}[/bold] {rname} ({cnt} finding{'s' if cnt != 1 else ''})")


def _render_next_steps(console: Console) -> None:
    console.print("")
    console.print(
        Panel(
            "[bold]Next steps[/bold]\n"
            "  [cyan]snowfort audit show --pillar Security[/cyan]     Drill into a pillar (WHY / AFFECTED / FIX)\n"
            "  [cyan]snowfort audit show --interactive[/cyan]          Reopen TUI to navigate cached results\n"
            "  [cyan]snowfort audit rules SEC_001[/cyan]              Full rule definition\n"
            "  [cyan]snowfort audit show -o report.yaml[/cyan]         Export YAML report\n"
            "  [cyan]snowfort audit show --severity CRITICAL[/cyan]  Filter cached results",
            border_style="dim",
        )
    )


def report_findings_guided(
    violations,
    rules,
    telemetry,
    manifest,
    target_name: str = ".",
    audit_metadata: dict | None = None,
    result: AuditResult | None = None,
    errored_count: int = 0,
) -> None:
    if manifest:
        _render_manifest_json(violations, telemetry, audit_metadata, rules=rules)
        return
    console = Console()
    result = result or AuditResult.from_violations(violations, metadata=audit_metadata or {})
    scorecard = result.scorecard
    _render_scorecard_guided(console, result, target_name)
    _render_pillar_table_guided(console, scorecard)
    if errored_count:
        console.print(f"[bold red]Warning: {errored_count} rule(s) errored — results may be incomplete.[/bold red]")
    if not violations:
        console.print("[green]Perfect Score: No WAF violations detected.[/green]")
        console.print("[dim]Run snowfort audit rules to see all 116 checks.[/dim]")
        return
    violations_by_rule: dict[str, list] = {}
    for v in violations:
        violations_by_rule.setdefault(v.rule_id, []).append(v)
    _render_pillar_checklists(console, violations, rules, scorecard)
    _render_top_actions(console, rules, violations_by_rule)
    _render_next_steps(console)


def report_pillar_detail(violations, rules, pillar_filter: str) -> None:
    console = Console()
    pillar_normalized = pillar_filter.strip().title()
    matching_pillars = [p for p in PILLAR_DISPLAY_ORDER if p.lower() == pillar_normalized.lower()]
    if not matching_pillars:
        opts = ", ".join(PILLAR_DISPLAY_ORDER)
        console.print(f"[yellow]Unknown pillar '{pillar_filter}'. Choose from: {opts}[/yellow]")
        return
    target_pillar = matching_pillars[0]
    groups = group_violations_by_concept(violations, rules)
    pillar_groups = [(r, vs) for r, vs in groups if (r.pillar or pillar_from_rule_id(r.id)) == target_pillar]

    if not pillar_groups:
        console.print(f"[green]No violations found for {target_pillar}.[/green]")
        return

    console.print(f"\n[bold cyan]{target_pillar}[/bold cyan] — {len(pillar_groups)} rule(s) with findings\n")
    for rule, group_violations in pillar_groups:
        sev = group_violations[0].severity if group_violations else rule.severity
        panel_title = f"{rule.name} ({rule.id}) — {sev.value}"
        why = rule.rationale or "No rationale available."
        affected_lines = [f"  [bold]{v.resource_name}[/bold]  {v.message}" for v in group_violations]
        fix_text = rule.remediation or "No remediation available."
        body = (
            f"[bold]WHY:[/bold] {why}\n\n[bold]AFFECTED ({len(group_violations)}):[/bold]\n"
            + "\n".join(affected_lines)
            + f"\n\n[bold]FIX:[/bold] {fix_text}"
        )
        console.print(Panel(body, title=panel_title, border_style=severity_border_style(sev)))
    console.print("\n[dim]snowfort audit rules <RULE_ID> for full rule definition.[/dim]")


def report_rule_detail(violations: list, rules: list, rule_id: str) -> None:
    console = Console()
    rule_id_upper = rule_id.upper().strip()
    match = next((r for r in rules if r.id.upper() == rule_id_upper), None)
    if not match:
        console.print(f"[red]No rule found: {rule_id}[/red]")
        return
    rule = match
    pv = [v for v in violations if v.rule_id.upper() == rule_id_upper]
    if not pv:
        console.print(f"[green]No violations for {rule.id}.[/green]")
        return
    sev = pv[0].severity
    panel_title = f"{rule.name} ({rule.id}) — {sev.value}"
    why = rule.rationale or "No rationale available."
    affected_lines = [f"  [bold]{v.resource_name}[/bold]  {v.message}" for v in pv]
    fix_text = rule.remediation or "No remediation available."
    body = (
        f"[bold]WHY:[/bold] {why}\n\n[bold]AFFECTED ({len(pv)}):[/bold]\n"
        + "\n".join(affected_lines)
        + f"\n\n[bold]FIX:[/bold] {fix_text}"
    )
    console.print(Panel(body, title=panel_title, border_style=severity_border_style(sev)))


def show_filtered_table(violations: list, target_name: str = "?", timestamp: str = "") -> None:
    console = Console()
    if not violations:
        console.print("[green]No violations match the filters.[/green]")
        return
    console.print(f"[dim]Cached: {target_name} @ {timestamp}[/dim] — [bold]{len(violations)}[/bold] violation(s)")
    table = Table(show_header=True, header_style="cyan")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Pillar", width=10)
    table.add_column("Rule", width=12)
    table.add_column("Resource", width=24)
    table.add_column("Message")
    for v in violations:
        sev_style = "[red]" if v.severity in (Severity.CRITICAL, Severity.HIGH) else "[yellow]"
        p = v.pillar or pillar_from_rule_id(v.rule_id)
        table.add_row(f"{sev_style}{v.severity.value}[/]", pillar_style(p), v.rule_id, v.resource_name, v.message)
    console.print(table)


def build_yaml_report(
    result: AuditResult,
    rules: list,
    project_root: Path,
    load_account_config_fn=None,
) -> dict:
    """Build YAML report dict. load_account_config_fn(project_root) if provided, else {} for account_cfg."""
    rules_by_id = {r.id: r for r in rules}
    findings = []
    for v in result.violations:
        r = rules_by_id.get(v.rule_id)
        findings.append(
            {
                "rule_id": v.rule_id,
                "rule_name": r.name if r else v.rule_id,
                "pillar": v.pillar or pillar_from_rule_id(v.rule_id),
                "severity": v.severity.value,
                "resource": v.resource_name,
                "message": v.message,
                **_enrichment_fields(v, r),
            }
        )
    try:
        account_cfg = load_account_config_fn(project_root) if load_account_config_fn else {}
    except Exception:
        account_cfg = {}
    sc = result.scorecard
    return {
        "snowfort_audit_report": {
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "account": result.metadata.get("account_id", ""),
            "account_topology": account_cfg.get("account_topology", ACCOUNT_TOPOLOGY_MULTI_ENV),
            "environments": account_cfg.get("environments", DEFAULT_ENVIRONMENTS),
            "summary": {
                "score": sc.compliance_score,
                "grade": sc.grade,
                "adjusted_score": sc.adjusted_score,
                "adjusted_grade": sc.adjusted_grade,
                "actionable_count": sc.actionable_count,
                "expected_count": sc.expected_count,
                "informational_count": sc.informational_count,
                "total_violations": sc.total_violations,
                "by_severity": {
                    "CRITICAL": sc.critical_count,
                    "HIGH": sc.high_count,
                    "MEDIUM": sc.medium_count,
                    "LOW": sc.low_count,
                },
            },
            "findings": findings,
            **({"cortex_summary": result.cortex_summary.to_dict()} if result.cortex_summary else {}),
        }
    }
