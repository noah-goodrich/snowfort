"""DI container: holds registrations; wiring is done by infrastructure.wiring.register_all()."""

from snowfort_audit._vendor.container import BaseContainer


class AuditContainer(BaseContainer):
    """DI Container for Snowarch Audit. Call infrastructure.wiring.register_all(container) after construction."""

    def __init__(self):
        super().__init__()
        self.register_telemetry(project_name="Snowfort", color="cyan", welcome_msg="WAF Audit")

    def _filter_rules_if_scan_rule_ids(self, rules: list) -> list:
        """Apply rule filtering. Rules with default_disabled=True are excluded
        unless the user explicitly opts them in via --rules."""
        try:
            scan_rule_ids = self.get("ScanRuleIds")
        except ValueError:
            scan_rule_ids = None
        if scan_rule_ids is None:
            return [r for r in rules if not getattr(r, "default_disabled", False)]
        return [r for r in rules if r.id in scan_rule_ids]

    def get_rules(self):
        evaluator = self.get("FinancialEvaluator")
        telemetry = self.get("TelemetryPort")
        try:
            custom_dir = self.get("CustomRulesDir")
        except ValueError:
            custom_dir = None
        try:
            permifrost_spec = self.get("PermifrostSpecPath")
        except ValueError:
            permifrost_spec = None
        get_rules_fn = self.get("get_rules_fn")
        rules = get_rules_fn(evaluator, telemetry, custom_dir, permifrost_spec_path=permifrost_spec)
        return self._filter_rules_if_scan_rule_ids(rules)
