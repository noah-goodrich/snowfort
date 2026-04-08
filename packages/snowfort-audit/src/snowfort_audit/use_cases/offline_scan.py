import time
from typing import Any

from snowfort_audit.domain.protocols import FileSystemProtocol, ManifestRepositoryProtocol, TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Violation

# (rule_id, rule_name, duration_seconds)
RuleTiming = tuple[str, str, float]


class OfflineScanUseCase:
    """Orchestrates the offline scan of Infrastructure-as-Code definitions."""

    def __init__(
        self,
        fs_gateway: FileSystemProtocol,
        manifest_repo: ManifestRepositoryProtocol,
        rules: list[Rule],
        telemetry: TelemetryPort,
    ):
        self.fs = fs_gateway
        self.manifest_repo = manifest_repo
        self.rules = rules
        self.telemetry = telemetry
        self.profile_timings: list[RuleTiming] = []

    def execute(self, path: str, profile: bool = False) -> list[Violation]:
        """Scans a directory for manifest.yml and validates against WAF rules.
        profile: if True, collect per-rule timing in self.profile_timings.
        """
        self.telemetry.step(f"Hull Inspection: Scanning definitions in {path}...")
        self.profile_timings = []

        definitions: dict[str, Any] = self.manifest_repo.load_definitions(path)

        violations: list[Violation] = []
        rule_elapsed: dict[str, float] = {}

        for name, resource in definitions.items():
            for rule in self.rules:
                t0 = time.perf_counter()
                try:
                    result = rule.check(resource, name)
                    current_violations = []
                    if isinstance(result, list):
                        current_violations = result
                    elif result:
                        current_violations = [result]

                    violations.extend(current_violations)
                except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as e:
                    self.telemetry.error(f"Rule {rule.id} failed on resource {name}: {e}")
                if profile:
                    rule_elapsed[rule.id] = rule_elapsed.get(rule.id, 0.0) + (time.perf_counter() - t0)

        # Static SQL Analysis
        sql_violations, sql_elapsed = self._scan_sql_files(path, profile)
        violations.extend(sql_violations)

        if profile:
            rule_name_map = {r.id: r.name for r in self.rules}
            for rule_id, elapsed in sql_elapsed.items():
                rule_elapsed[rule_id] = rule_elapsed.get(rule_id, 0.0) + elapsed
            self.profile_timings = [
                (rid, rule_name_map.get(rid, rid), elapsed) for rid, elapsed in rule_elapsed.items()
            ]

        return violations

    def _scan_sql_files(self, path: str, profile: bool = False) -> tuple[list[Violation], dict[str, float]]:
        """Walks the directory for SQL files and runs static analysis rules."""
        violations: list[Violation] = []
        rule_elapsed: dict[str, float] = {}

        for root, _, files in self.fs.walk(path):
            for file in files:
                if file.endswith((".sql", ".sql.j2", ".py")):
                    file_path = self.fs.join_path(root, file)
                    file_violations, file_elapsed = self._analyze_single_sql_file(file_path, profile)
                    violations.extend(file_violations)
                    if profile:
                        for rule_id, elapsed in file_elapsed.items():
                            rule_elapsed[rule_id] = rule_elapsed.get(rule_id, 0.0) + elapsed

        return violations, rule_elapsed

    def _analyze_single_sql_file(
        self, file_path: str, profile: bool = False
    ) -> tuple[list[Violation], dict[str, float]]:
        """Reads and analyzes a single SQL file against all rules."""
        violations: list[Violation] = []
        rule_elapsed: dict[str, float] = {}
        try:
            content = self.fs.read_text(file_path)

            for rule in self.rules:
                t0 = time.perf_counter()
                result = rule.check_static(content, file_path)
                if result:
                    violations.extend(result)
                if profile:
                    rule_elapsed[rule.id] = rule_elapsed.get(rule.id, 0.0) + (time.perf_counter() - t0)
        except (OSError, UnicodeDecodeError) as e:
            self.telemetry.error(f"Failed to read SQL file {file_path}: {e}")
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as e:
            self.telemetry.error(f"Unexpected error analyzing SQL file {file_path}: {e}")

        return violations, rule_elapsed
