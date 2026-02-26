from typing import Any

from snowfort_audit.domain.protocols import FileSystemProtocol, ManifestRepositoryProtocol, TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule, Violation


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

    def execute(self, path: str) -> list[Violation]:
        """Scans a directory for manifest.yml and validates against WAF rules."""
        self.telemetry.step(f"Hull Inspection: Scanning definitions in {path}...")

        definitions: dict[str, Any] = self.manifest_repo.load_definitions(path)

        violations: list[Violation] = []

        for name, resource in definitions.items():
            for rule in self.rules:
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

        # Static SQL Analysis
        sql_violations = self._scan_sql_files(path)
        violations.extend(sql_violations)

        return violations

    def _scan_sql_files(self, path: str) -> list[Violation]:
        """Walks the directory for SQL files and runs static analysis rules."""
        violations: list[Violation] = []

        for root, _, files in self.fs.walk(path):
            for file in files:
                if file.endswith((".sql", ".sql.j2", ".py")):
                    file_path = self.fs.join_path(root, file)
                    violations.extend(self._analyze_single_sql_file(file_path))

        return violations

    def _analyze_single_sql_file(self, file_path: str) -> list[Violation]:
        """Reads and analyzes a single SQL file against all rules."""
        violations: list[Violation] = []
        try:
            content = self.fs.read_text(file_path)

            for rule in self.rules:
                result = rule.check_static(content, file_path)
                if result:
                    violations.extend(result)
        except (OSError, UnicodeDecodeError) as e:
            self.telemetry.error(f"Failed to read SQL file {file_path}: {e}")
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as e:
            self.telemetry.error(f"Unexpected error analyzing SQL file {file_path}: {e}")

        return violations
