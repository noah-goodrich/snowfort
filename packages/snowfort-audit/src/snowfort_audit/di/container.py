"""DI container: holds registrations; wiring is done by infrastructure.wiring.register_all()."""

from snowfort_audit._vendor.container import BaseContainer


class AuditContainer(BaseContainer):
    """DI Container for Snowarch Audit. Call infrastructure.wiring.register_all(container) after construction."""

    def __init__(self):
        super().__init__()
        self.register_telemetry(project_name="Snowfort", color="cyan", welcome_msg="WAF Audit")

    def _filter_rules_if_scan_rule_ids(self, rules: list) -> list:
        try:
            scan_rule_ids = self.get("ScanRuleIds")
        except ValueError:
            return rules
        if scan_rule_ids is None:
            return rules
        return [r for r in rules if r.id in scan_rule_ids]

    def get_rules(self):
        evaluator = self.get("FinancialEvaluator")
        telemetry = self.get("TelemetryPort")
        try:
            custom_dir = self.get("CustomRulesDir")
        except ValueError:
            custom_dir = None
        get_rules_fn = self.get("get_rules_fn")
        rules = get_rules_fn(evaluator, telemetry, custom_dir)
        return self._filter_rules_if_scan_rule_ids(rules)
