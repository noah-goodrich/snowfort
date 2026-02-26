from snowfort_audit.domain.rule_definitions import Rule, Severity, Violation


class MyCustomRule(Rule):
    def __init__(self):
        super().__init__(
            rule_id="CUST_001",
            name="My Custom Rule",
            severity=Severity.HIGH,
            rationale="Custom rationale.",
            remediation="Custom remediation.",
        )

    def check_static(self, file_content: str, file_path: str) -> list[Violation]:
        if "forbidden_term" in file_content:
            return [
                Violation(
                    rule_id=self.id, resource_name=file_path, message="Found forbidden term!", severity=self.severity
                )
            ]
        return []


def get_rules() -> list:
    return [MyCustomRule()]
