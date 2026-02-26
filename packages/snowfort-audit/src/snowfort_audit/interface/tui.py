"""Interactive TUI for navigating Snowfort Audit results.

Uses textual to provide keyboard-driven drill-down:
  Overview (pillar or severity) → Pillar/Severity detail (rule panels) → Rule detail (full info + conventions).
  Export to YAML and toggle view (pillar-first vs severity-first) when container/project_root provided.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import yaml
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, ListItem, ListView, Static

from snowfort_audit.domain.guided import group_violations_by_concept
from snowfort_audit.domain.results import AuditResult
from snowfort_audit.domain.rule_definitions import (
    PILLAR_DISPLAY_ORDER,
    Rule,
    Severity,
    Violation,
    pillar_from_rule_id,
)
from snowfort_audit.interface.cli.report import conventions_for_pillar

_SEV_WEIGHT = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
_SEV_ORDER: tuple[Severity, ...] = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)


def _bar(value: float, width: int = 20) -> str:
    filled = round(value / 100 * width)
    if value >= 90:
        color = "green"
    elif value >= 70:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{'━' * filled}[/{color}][dim]{'━' * (width - filled)}[/dim]"


def _sev_color(sev: Severity) -> str:
    return "red" if sev in (Severity.CRITICAL, Severity.HIGH) else "yellow"


def _status_label(grade: str) -> str:
    """Human-readable status for overview: Critical, Review, or Healthy."""
    if grade == "A":
        return "[green]Healthy[/green]"
    if grade in ("B", "C"):
        return "[yellow]Review[/yellow]"
    return "[red]Critical[/red]"


class PillarListItem(ListItem):
    """A pillar row in the overview list."""

    def __init__(self, pillar: str, score: float, grade: str, failed: int, total: int) -> None:
        super().__init__()
        self.pillar = pillar
        self.score = score
        self.grade = grade
        self.failed = failed
        self.total = total

    def compose(self) -> ComposeResult:
        bar = _bar(self.score, 15)
        status = _status_label(self.grade)
        if self.failed:
            detail = f"{status}  ({self.failed} finding{'s' if self.failed != 1 else ''})"
        else:
            detail = f"{status}  (all {self.total} passed)"
        yield Static(f"  [bold]{self.pillar:<14}[/bold] {int(self.score):>3}/100 {bar}  {self.grade}  {detail}")


class SeverityListItem(ListItem):
    """A severity row in overview (severity-first view)."""

    def __init__(self, severity: Severity, count: int) -> None:
        super().__init__()
        self.severity = severity
        self.count = count

    def compose(self) -> ComposeResult:
        sc = "[red]" if self.severity in (Severity.CRITICAL, Severity.HIGH) else "[yellow]"
        yield Static(f"  {sc}{self.severity.value:<10}[/]  {self.count} violation(s)")


class RulePanelListItem(ListItem):
    """Selectable rule panel in pillar/severity detail (Enter → rule detail)."""

    def __init__(self, rule: Rule, gvs: list[Violation], sev_cls: str, body: str) -> None:
        super().__init__()
        self.rule = rule
        self.gvs = gvs
        self._sev_cls = sev_cls
        self._body = body

    def compose(self) -> ComposeResult:
        yield Static(self._body, classes=f"rule-panel {self._sev_cls}")


class AuditTUI(App):
    """Keyboard-driven audit result explorer."""

    CSS = """
    Screen { background: $surface; }
    #overview { height: 1fr; }
    #detail-scroll { height: 1fr; padding: 1 2; }
    .pillar-header { text-style: bold; color: cyan; padding: 1 0 0 0; }
    .rule-panel { margin: 0 0 1 0; padding: 1 2; border: round $accent; }
    .rule-panel-critical { border: round red; }
    .rule-panel-high { border: round red; }
    .rule-panel-medium { border: round yellow; }
    .rule-panel-low { border: round $accent; }
    .top-action { padding: 0 0 0 2; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "back", "Back"),
        Binding("v", "view_toggle", "Pillar/Severity"),
        Binding("e", "export_yaml", "Export YAML"),
    ]

    def __init__(
        self,
        result: AuditResult,
        rules: list[Rule],
        violations: list[Violation],
        container: Any = None,
        project_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.rules = rules
        self.violations = violations
        self._container = container
        self._project_root = project_root or Path.cwd()
        self._current_view = "overview"
        self._view_mode: str = "pillar"  # "pillar" | "severity"
        self._detail_context: str | None = None  # "pillar:Security" or "severity:CRITICAL"

        self._violations_by_rule: dict[str, list[Violation]] = {}
        for v in violations:
            self._violations_by_rule.setdefault(v.rule_id, []).append(v)

        self._rules_by_pillar: dict[str, list[Rule]] = {}
        for r in rules:
            p = r.pillar or pillar_from_rule_id(r.id)
            if p not in PILLAR_DISPLAY_ORDER:
                p = "Other"
            self._rules_by_pillar.setdefault(p, []).append(r)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ListView(id="overview")
        yield VerticalScroll(id="detail-scroll")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Snowfort Audit"
        sc = self.result.scorecard
        self.sub_title = f"Score: {sc.compliance_score}/100 ({sc.grade})"
        self._show_overview()

    def _show_overview(self) -> None:
        self._current_view = "overview"
        self._detail_context = None
        lv = self.query_one("#overview", ListView)
        ds = self.query_one("#detail-scroll", VerticalScroll)
        ds.display = False
        lv.display = True
        lv.clear()

        sc = self.result.scorecard
        bar = _bar(sc.compliance_score, 25)
        mode_hint = " (Severity-first)" if self._view_mode == "severity" else " (Pillar-first)"
        overall = f"\n  [bold]Overall: {sc.compliance_score}/100 ({sc.grade})[/bold]  {bar} [dim]{mode_hint}[/dim]\n"
        lv.append(ListItem(Static(overall), disabled=True))

        if self._view_mode == "severity":
            for sev in _SEV_ORDER:
                count = (
                    sc.critical_count
                    if sev == Severity.CRITICAL
                    else sc.high_count
                    if sev == Severity.HIGH
                    else sc.medium_count
                    if sev == Severity.MEDIUM
                    else sc.low_count
                )
                lv.append(SeverityListItem(sev, count))
        else:
            for p in PILLAR_DISPLAY_ORDER:
                pscore = sc.pillar_scores.get(p, 100.0)
                pgrade = sc.pillar_grades.get(p, "A")
                p_rules = self._rules_by_pillar.get(p, [])
                failed = sum(1 for r in p_rules if r.id in self._violations_by_rule)
                lv.append(PillarListItem(p, pscore, pgrade, failed, len(p_rules)))

        # Top 3 actions
        rule_impact: list[tuple[int, int, str, str, str]] = []
        for r in self.rules:
            pv = self._violations_by_rule.get(r.id, [])
            if not pv:
                continue
            worst = min(pv, key=lambda v: _SEV_WEIGHT.get(v.severity, 9)).severity
            rule_impact.append((_SEV_WEIGHT[worst], len(pv), r.id, r.name, worst.value))
        rule_impact.sort(key=lambda x: (x[0], -x[1]))
        top = rule_impact[:3]
        if top:
            lv.append(ListItem(Static("\n  [bold]Top 3 actions[/bold]"), disabled=True))
            for i, (_, cnt, rid, rname, sval) in enumerate(top, 1):
                sc_txt = "[red]" if sval in ("CRITICAL", "HIGH") else "[yellow]"
                line = f"    {i}. {sc_txt}{sval}[/] [bold]{rid}[/bold] {rname} ({cnt})"
                lv.append(ListItem(Static(line), disabled=True))

        lv.append(
            ListItem(Static("\n[dim]v: toggle Pillar/Severity  e: Export YAML (when available)[/dim]"), disabled=True)
        )
        lv.index = 1
        self.set_focus(lv)

    def _show_pillar(self, pillar: str) -> None:
        self._current_view = "detail"
        self._detail_context = f"pillar:{pillar}"
        lv = self.query_one("#overview", ListView)
        ds = self.query_one("#detail-scroll", VerticalScroll)
        lv.display = False
        ds.display = True
        ds.remove_children()

        sc = self.result.scorecard
        pscore = sc.pillar_scores.get(pillar, 100.0)
        pgrade = sc.pillar_grades.get(pillar, "A")
        bar = _bar(pscore, 20)
        ds.mount(Static(f"\n[bold cyan]{pillar}[/bold cyan]  {int(pscore)}/100 ({pgrade})  {bar}\n"))

        groups = group_violations_by_concept(self.violations, self.rules)
        pillar_groups = [(r, vs) for r, vs in groups if (r.pillar or pillar_from_rule_id(r.id)) == pillar]

        if not pillar_groups:
            ds.mount(Static("[green]No violations found.[/green]"))
            ds.mount(Static("\n[dim]Press Escape to return.[/dim]"))
            return

        items = []
        for rule, gvs in pillar_groups:
            sev = gvs[0].severity if gvs else rule.severity
            sev_cls = f"rule-panel-{sev.value.lower()}"
            why = rule.rationale or "No rationale available."
            affected = "\n".join(f"  [bold]{v.resource_name}[/bold]  {v.message}" for v in gvs)
            fix = rule.remediation or "No remediation available."
            body = (
                f"[bold]{rule.name}[/bold] ({rule.id}) — [{_sev_color(sev)}]{sev.value}[/]\n\n"
                f"[bold]WHY:[/bold] {why}\n\n"
                f"[bold]AFFECTED ({len(gvs)}):[/bold]\n{affected}\n\n"
                f"[bold]FIX:[/bold] {fix}"
            )
            items.append(RulePanelListItem(rule, gvs, sev_cls, body))
        detail_list = ListView()
        ds.mount(detail_list)
        self.run_worker(self._populate_list_view(detail_list, items))
        ds.mount(Static("\n[dim]Enter: rule detail  Escape: back[/dim]"))

    def _show_severity_detail(self, severity: Severity) -> None:
        self._current_view = "detail"
        self._detail_context = f"severity:{severity.value}"
        lv = self.query_one("#overview", ListView)
        ds = self.query_one("#detail-scroll", VerticalScroll)
        lv.display = False
        ds.display = True
        ds.remove_children()

        groups = group_violations_by_concept(self.violations, self.rules)
        sev_groups = [(r, vs) for r, vs in groups if vs and vs[0].severity == severity]
        sc_txt = "[red]" if severity in (Severity.CRITICAL, Severity.HIGH) else "[yellow]"
        ds.mount(
            Static(f"\n{sc_txt}[bold]{severity.value}[/bold][/]  {sum(len(vs) for _, vs in sev_groups)} violation(s)\n")
        )

        if not sev_groups:
            ds.mount(Static("[green]No violations for this severity.[/green]"))
            ds.mount(Static("\n[dim]Press Escape to return.[/dim]"))
            return

        items = []
        for rule, gvs in sev_groups:
            sev_cls = f"rule-panel-{severity.value.lower()}"
            why = rule.rationale or "No rationale available."
            affected = "\n".join(f"  [bold]{v.resource_name}[/bold]  {v.message}" for v in gvs)
            fix = rule.remediation or "No remediation available."
            body = (
                f"[bold]{rule.name}[/bold] ({rule.id}) — [{_sev_color(severity)}]{severity.value}[/]\n\n"
                f"[bold]WHY:[/bold] {why}\n\n"
                f"[bold]AFFECTED ({len(gvs)}):[/bold]\n{affected}\n\n"
                f"[bold]FIX:[/bold] {fix}"
            )
            items.append(RulePanelListItem(rule, gvs, sev_cls, body))
        detail_list = ListView()
        ds.mount(detail_list)
        self.run_worker(self._populate_list_view(detail_list, items))
        ds.mount(Static("\n[dim]Enter: rule detail  Escape: back[/dim]"))

    async def _populate_list_view(self, list_view: ListView, items: Sequence[ListItem]) -> None:
        """Append items to a ListView after it is mounted (must await each append)."""
        for item in items:
            await list_view.append(item)
        if items:
            list_view.index = 0
        self.set_focus(list_view)

    def _show_rule_detail(self, rule_id: str) -> None:
        self._current_view = "rule_detail"
        lv = self.query_one("#overview", ListView)
        ds = self.query_one("#detail-scroll", VerticalScroll)
        lv.display = False
        ds.display = True
        ds.remove_children()

        rule = next((r for r in self.rules if r.id.upper() == rule_id.upper()), None)
        if not rule:
            ds.mount(Static(f"[red]Rule not found: {rule_id}[/red]"))
            ds.mount(Static("\n[dim]Press Escape to return.[/dim]"))
            return

        lines = [
            f"[bold cyan]Rule: {rule.id}[/bold cyan]",
            f"  [bold]ID[/bold]        {rule.id}",
            f"  [bold]Name[/bold]     {rule.name}",
            f"  [bold]Severity[/bold] {rule.severity.value}",
            f"  [bold]Pillar[/bold]   {rule.pillar or pillar_from_rule_id(rule.id)}",
            f"  [bold]Rationale[/bold]   {rule.rationale or '(none)'}",
            f"  [bold]Remediation[/bold] {rule.remediation or '(none)'}",
        ]
        if rule.remediation_key:
            lines.append(f"  [dim]Remediation key: {rule.remediation_key}[/dim]")
        ds.mount(Static("\n".join(lines)))

        if self._container:
            try:
                load_conventions = self._container.get("load_conventions")
                conv = load_conventions(self._project_root)
                conv_lines = conventions_for_pillar(rule.pillar or pillar_from_rule_id(rule.id), conv)
                if conv_lines:
                    ds.mount(Static("\n[bold]Conventions (pillar)[/bold]"))
                    for key, val in conv_lines:
                        ds.mount(Static(f"  [cyan]{key}[/cyan]  {val}"))
                    ds.mount(Static("[dim]Override in pyproject.toml: [tool.snowfort.conventions][/dim]"))
            except Exception:
                pass
        ds.mount(Static("\n[dim]Press Escape to return.[/dim]"))

    @on(ListView.Selected)
    def _on_select(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, PillarListItem):
            self._show_pillar(item.pillar)
        elif isinstance(item, SeverityListItem):
            self._show_severity_detail(item.severity)
        elif isinstance(item, RulePanelListItem):
            self._show_rule_detail(item.rule.id)

    async def action_back(self) -> None:
        if self._current_view == "rule_detail":
            self._current_view = "detail"
            if self._detail_context and self._detail_context.startswith("pillar:"):
                self._show_pillar(self._detail_context.split(":", 1)[1])
            elif self._detail_context and self._detail_context.startswith("severity:"):
                self._show_severity_detail(Severity(self._detail_context.split(":", 1)[1]))
            return
        if self._current_view == "detail":
            self._show_overview()

    async def action_export_yaml(self) -> None:
        if not self._container or not self._project_root:
            return
        try:
            from snowfort_audit.interface.cli.report import build_yaml_report

            report_data = build_yaml_report(
                self.result,
                self.rules,
                self._project_root,
                load_account_config_fn=self._container.get("load_account_config"),
            )
            out = self._project_root / "report.yaml"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                yaml.dump(report_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
            self.notify(f"Exported to {out}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    async def action_view_toggle(self) -> None:
        self._view_mode = "severity" if self._view_mode == "pillar" else "pillar"
        self._show_overview()

    async def action_quit(self) -> None:
        self.exit()


def run_interactive(
    result: AuditResult,
    rules: list[Rule],
    violations: list[Violation],
    container: Any = None,
    project_root: Path | None = None,
) -> None:
    """Launch the interactive TUI. Optional container and project_root enable export and rule conventions."""
    app = AuditTUI(result, rules, violations, container=container, project_root=project_root)
    app.run()
