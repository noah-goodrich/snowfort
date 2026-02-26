import statistics
from dataclasses import dataclass, field

from snowfort_audit.domain.rule_definitions import (
    PILLAR_DISPLAY_ORDER,
    Severity,
    Violation,
    pillar_from_rule_id,
)


def _score_to_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _pillar_deduction(critical: int, high: int, medium: int, low: int) -> int:
    """Same deduction formula as overall: Critical -10, High -5, Medium -2, Low -1."""
    return (critical * 10) + (high * 5) + (medium * 2) + (low * 1)


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

    @property
    def grade(self) -> str:
        """Letter grade (A-F) derived from overall compliance score."""
        return _score_to_grade(float(self.compliance_score))

    @classmethod
    def from_violations(cls, violations: list[Violation]) -> "AuditScorecard":
        total = len(violations)
        critical = sum(1 for v in violations if v.severity == Severity.CRITICAL)
        high = sum(1 for v in violations if v.severity == Severity.HIGH)
        medium = sum(1 for v in violations if v.severity == Severity.MEDIUM)
        low = sum(1 for v in violations if v.severity == Severity.LOW)

        deduction = _pillar_deduction(critical, high, medium, low)
        score = max(0, 100 - deduction)

        # Per-pillar scores: group violations by pillar (derive from rule_id when pillar empty)
        pillar_violations: dict[str, list[Violation]] = {}
        for v in violations:
            p = v.pillar or pillar_from_rule_id(v.rule_id)
            pillar_violations.setdefault(p, []).append(v)
        pillar_scores: dict[str, float] = {}
        pillar_grades_dict: dict[str, str] = {}
        for p, pv in pillar_violations.items():
            c = sum(1 for v in pv if v.severity == Severity.CRITICAL)
            h = sum(1 for v in pv if v.severity == Severity.HIGH)
            m = sum(1 for v in pv if v.severity == Severity.MEDIUM)
            lo = sum(1 for v in pv if v.severity == Severity.LOW)
            ded = _pillar_deduction(c, h, m, lo)
            s = max(0, 100 - ded)
            pillar_scores[p] = float(s)
            pillar_grades_dict[p] = _score_to_grade(s)
        # Ensure all canonical pillars appear (score 100 / A when no violations)
        for p in PILLAR_DISPLAY_ORDER:
            if p not in pillar_scores:
                pillar_scores[p] = 100.0
                pillar_grades_dict[p] = "A"

        overall = round(statistics.mean(pillar_scores.values())) if pillar_scores else score
        return cls(
            compliance_score=overall,
            total_violations=total,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            pillar_scores=pillar_scores,
            pillar_grades=pillar_grades_dict,
        )


@dataclass(frozen=True)
class AuditResult:
    violations: list[Violation] = field(default_factory=list)
    scorecard: AuditScorecard = field(default_factory=AuditScorecard)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_violations(
        cls,
        violations: list[Violation],
        metadata: dict | None = None,
    ) -> "AuditResult":
        scorecard = AuditScorecard.from_violations(violations)
        return cls(
            violations=violations,
            scorecard=scorecard,
            metadata=metadata or {},
        )

    def to_summary_dict(self) -> dict[str, int]:
        return {
            "COMPLIANCE_SCORE": self.scorecard.compliance_score,
            "TOTAL_VIOLATIONS": self.scorecard.total_violations,
            "CRITICAL_COUNT": self.scorecard.critical_count,
            "HIGH_COUNT": self.scorecard.high_count,
        }
