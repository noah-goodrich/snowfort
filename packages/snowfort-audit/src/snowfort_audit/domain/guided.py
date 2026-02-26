"""Guided (concept-grouped) reporting helpers."""

from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation

# Severity order for sorting (highest first)
_SEVERITY_ORDER = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)


def _severity_rank(severity: Severity) -> int:
    """Lower rank = higher priority (CRITICAL=0)."""
    try:
        return _SEVERITY_ORDER.index(severity)
    except ValueError:
        return len(_SEVERITY_ORDER)


def group_violations_by_concept(
    violations: list[Violation],
    rules: list[Rule],
) -> list[tuple[Rule, list[Violation]]]:
    """Group violations by rule_id, ordered by severity then pillar then rule_id.

    Returns (Rule, violations_for_that_rule) pairs. Violations whose rule_id
    is not in rules are grouped under a synthetic Unknown rule.
    """
    rule_by_id: dict[str, Rule] = {r.id: r for r in rules}

    # Synthetic rule for violations with no matching Rule
    unknown_rule = Rule(
        "UNKNOWN",
        "Unknown",
        Severity.LOW,
        rationale="Rule metadata not found.",
        remediation="Check rule registry.",
    )

    groups: dict[str, list[Violation]] = {}
    for v in violations:
        rid = v.rule_id
        if rid not in groups:
            groups[rid] = []
        groups[rid].append(v)

    result: list[tuple[Rule, list[Violation]]] = []
    for rule_id, group_violations in groups.items():
        rule = rule_by_id.get(rule_id, unknown_rule)
        if rule is unknown_rule and rule_id != "UNKNOWN":
            # First time we see this unknown rule_id: use a placeholder Rule with that id
            rule = Rule(
                rule_id,
                f"Unknown ({rule_id})",
                group_violations[0].severity if group_violations else Severity.LOW,
                rationale="Rule metadata not found.",
                remediation="Check rule registry.",
            )
        result.append((rule, group_violations))

    # Sort: by severity (CRITICAL first), then pillar, then rule_id
    def sort_key(item: tuple[Rule, list[Violation]]) -> tuple[int, str, str]:
        r, vlist = item
        # Use worst severity in the group
        sev = min((v.severity for v in vlist), key=_severity_rank)
        return (_severity_rank(sev), r.pillar, r.id)

    result.sort(key=sort_key)
    return result
