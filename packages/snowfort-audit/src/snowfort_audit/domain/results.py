import math
import statistics
from dataclasses import dataclass, field

from snowfort_audit.domain.rule_definitions import (
    PILLAR_DISPLAY_ORDER,
    FindingCategory,
    Severity,
    Violation,
    pillar_from_rule_id,
)

# Dampening constant for log-scaled scoring.  Calibrated so that ~454 real
# violations across multiple pillars (the INCLOUDCOUNSEL baseline) produce an
# overall score in the 55-65 range (D/C boundary).
_LOG_DAMPENING_K = 10.0

# Score thresholds for letter grades. Exposed so UI layers (CLI report, TUI)
# can derive their colour boundaries from the same policy values rather than
# duplicating the cutoffs.
GRADE_A_MIN: float = 90.0
GRADE_B_MIN: float = 80.0
GRADE_C_MIN: float = 70.0
GRADE_D_MIN: float = 60.0


def _score_to_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    if score >= GRADE_A_MIN:
        return "A"
    if score >= GRADE_B_MIN:
        return "B"
    if score >= GRADE_C_MIN:
        return "C"
    if score >= GRADE_D_MIN:
        return "D"
    return "F"


def _pillar_deduction(critical: int, high: int, medium: int, low: int) -> int:
    """Raw severity-weighted deduction (unbounded). Used as input to log dampening."""
    return (critical * 10) + (high * 5) + (medium * 2) + (low * 1)


def _pillar_score(critical: int, high: int, medium: int, low: int) -> float:
    """Compute a 0-100 pillar score using logarithmic dampening.

    Formula: ``score = max(0, 100 - min(100, K * ln(1 + raw)))``
    where ``raw = critical*10 + high*5 + medium*2 + low*1``.

    This prevents high-volume, low-severity violations from instantly flooring
    the score while still penalising critical findings heavily.
    """
    raw = _pillar_deduction(critical, high, medium, low)
    if raw == 0:
        return 100.0
    dampened = min(100.0, _LOG_DAMPENING_K * math.log(1 + raw))
    return max(0.0, 100.0 - dampened)


_SEV_INDEX = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


def _count_violations(
    violations: list[Violation],
) -> tuple[tuple[int, int, int, int, int], dict[str, list[int]], tuple[int, int, int], dict[str, list[int]]]:
    """Single pass over violations returning (totals, pillar_counts, category_counts, actionable_pillar_counts).

    totals = (total, critical, high, medium, low)
    pillar_counts = {pillar: [critical, high, medium, low]}  (all violations)
    category_counts = (actionable, expected, informational)
    actionable_pillar_counts = {pillar: [critical, high, medium, low]}  (ACTIONABLE only)
    """
    total = critical = high = medium = low = 0
    actionable = expected = informational = 0
    pillar_counts: dict[str, list[int]] = {}
    actionable_pillar_counts: dict[str, list[int]] = {}
    for v in violations:
        total += 1
        idx = _SEV_INDEX.get(v.severity, 3)
        if idx == 0:
            critical += 1
        elif idx == 1:
            high += 1
        elif idx == 2:
            medium += 1
        else:
            low += 1
        p = v.pillar or pillar_from_rule_id(v.rule_id)
        counts = pillar_counts.get(p)
        if counts is None:
            counts = [0, 0, 0, 0]
            pillar_counts[p] = counts
        counts[idx] += 1

        if v.category == FindingCategory.ACTIONABLE:
            actionable += 1
            act_counts = actionable_pillar_counts.get(p)
            if act_counts is None:
                act_counts = [0, 0, 0, 0]
                actionable_pillar_counts[p] = act_counts
            act_counts[idx] += 1
        elif v.category == FindingCategory.EXPECTED:
            expected += 1
        else:
            informational += 1
    return (
        (total, critical, high, medium, low),
        pillar_counts,
        (actionable, expected, informational),
        actionable_pillar_counts,
    )


def _compute_pillar_scores(
    pillar_counts: dict[str, list[int]],
) -> tuple[dict[str, float], dict[str, str]]:
    """Compute per-pillar scores and grades from severity counts."""
    pillar_scores: dict[str, float] = {}
    pillar_grades: dict[str, str] = {}
    for p, counts in pillar_counts.items():
        s = _pillar_score(counts[0], counts[1], counts[2], counts[3])
        pillar_scores[p] = s
        pillar_grades[p] = _score_to_grade(s)
    for p in PILLAR_DISPLAY_ORDER:
        if p not in pillar_scores:
            pillar_scores[p] = 100.0
            pillar_grades[p] = "A"
    return pillar_scores, pillar_grades


@dataclass(frozen=True)
class AuditScorecard:
    compliance_score: int = 100
    total_violations: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    pillar_scores: dict[str, float] = field(default_factory=dict)
    pillar_grades: dict[str, str] = field(default_factory=dict)
    adjusted_score: int = 100
    actionable_count: int = 0
    expected_count: int = 0
    informational_count: int = 0

    @property
    def grade(self) -> str:
        """Letter grade (A-F) derived from overall compliance score."""
        return _score_to_grade(float(self.compliance_score))

    @property
    def adjusted_grade(self) -> str:
        """Letter grade (A-F) derived from adjusted (ACTIONABLE-only) score."""
        return _score_to_grade(float(self.adjusted_score))

    @classmethod
    def from_violations(cls, violations: list[Violation]) -> "AuditScorecard":
        totals, pillar_counts, category_counts, actionable_pillar_counts = _count_violations(violations)
        pillar_scores, pillar_grades_dict = _compute_pillar_scores(pillar_counts)
        overall = round(statistics.mean(pillar_scores.values())) if pillar_scores else 100

        # Adjusted score: same formula but only ACTIONABLE violations
        adj_pillar_scores, _ = _compute_pillar_scores(actionable_pillar_counts)
        adjusted = round(statistics.mean(adj_pillar_scores.values())) if adj_pillar_scores else 100

        return cls(
            compliance_score=overall,
            total_violations=totals[0],
            critical_count=totals[1],
            high_count=totals[2],
            medium_count=totals[3],
            low_count=totals[4],
            pillar_scores=pillar_scores,
            pillar_grades=pillar_grades_dict,
            adjusted_score=adjusted,
            actionable_count=category_counts[0],
            expected_count=category_counts[1],
            informational_count=category_counts[2],
        )


@dataclass(frozen=True)
class CortexSummary:
    """Structured Cortex executive summary persisted in the YAML report."""

    tl_dr: str = ""
    top_risks: list[str] = field(default_factory=list)
    quick_wins: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tl_dr": self.tl_dr,
            "top_risks": list(self.top_risks),
            "quick_wins": list(self.quick_wins),
        }


_UNRELIABLE_ERROR_THRESHOLD = 0.05


@dataclass(frozen=True)
class AuditResult:
    violations: list[Violation] = field(default_factory=list)
    scorecard: AuditScorecard = field(default_factory=AuditScorecard)
    metadata: dict = field(default_factory=dict)
    cortex_summary: "CortexSummary | None" = field(default=None)
    errored_rules: tuple[str, ...] = field(default_factory=tuple)
    total_rules_executed: int = 0

    @property
    def reliable(self) -> bool:
        """True when the scan error rate is at or below the 5% threshold."""
        if self.total_rules_executed == 0:
            return True
        return len(self.errored_rules) / self.total_rules_executed <= _UNRELIABLE_ERROR_THRESHOLD

    @classmethod
    def from_violations(
        cls,
        violations: list[Violation],
        metadata: dict | None = None,
        errored_rules: list[str] | None = None,
        total_rules_executed: int = 0,
    ) -> "AuditResult":
        scorecard = AuditScorecard.from_violations(violations)
        return cls(
            violations=violations,
            scorecard=scorecard,
            metadata=metadata or {},
            errored_rules=tuple(errored_rules) if errored_rules else (),
            total_rules_executed=total_rules_executed,
        )

    def to_summary_dict(self) -> dict[str, int]:
        return {
            "COMPLIANCE_SCORE": self.scorecard.compliance_score,
            "TOTAL_VIOLATIONS": self.scorecard.total_violations,
            "CRITICAL_COUNT": self.scorecard.critical_count,
            "HIGH_COUNT": self.scorecard.high_count,
        }
