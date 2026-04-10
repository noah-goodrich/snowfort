from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from snowfort_audit.domain.rule_definitions import RuleExecutionError
from snowfort_audit.domain.rules.cost import (
    AggressiveAutoSuspendCheck,
    CloudServicesRatioCheck,
    HighChurnPermanentTableCheck,
    MultiClusterSafeguardCheck,
    PerWarehouseStatementTimeoutCheck,
    RunawayQueryCheck,
    StaleTableDetectionCheck,
    UnderutilizedWarehouseCheck,
    ZombieWarehouseCheck,
)
from snowfort_audit.domain.rules.op_excellence import (
    AlertConfigurationCheck,
    AlertExecutionReliabilityCheck,
    DataMetricFunctionsCoverageCheck,
    EventTableConfigurationCheck,
    IaCDriftReadinessCheck,
    NotificationIntegrationCheck,
    ObjectCommentCheck,
    ObservabilityInfrastructureCheck,
    ResourceMonitorCheck,
)
from snowfort_audit.domain.rules.perf import LocalSpillageCheck, QueryLatencySLOCheck, RemoteSpillageCheck
from snowfort_audit.domain.rules.reliability import (
    AdequateTimeTravelRetentionCheck,
    ReplicationCheck,
    RetentionSafetyCheck,
    SchemaEvolutionCheck,
)
from snowfort_audit.domain.rules.security import (
    AdminExposureCheck,
    DataExfiltrationPreventionCheck,
    FederatedAuthenticationCheck,
    MFAEnforcementCheck,
    NetworkPerimeterCheck,
    PasswordPolicyCheck,
    PrivateConnectivityCheck,
    PublicGrantsCheck,
    ServiceUserSecurityCheck,
    SSOCoverageCheck,
    UserOwnershipCheck,
    ZombieRoleCheck,
    ZombieUserCheck,
)
from snowfort_audit.domain.rules.static import HardcodedEnvCheck, NakedDropCheck, SecretExposureCheck, SelectStarCheck

EXPECTED_VIOLATIONS = 2


class TestCostRules:
    def test_aggressive_auto_suspend_check(self):
        rule = AggressiveAutoSuspendCheck()
        res = {"type": "WAREHOUSE", "auto_suspend": "120"}
        assert len(rule.check(res, "WH_DEV")) == 1
        res = {"type": "WAREHOUSE", "auto_suspend": "600"}
        assert len(rule.check(res, "WH_PRD")) == 1
        # 30s is now within convention (threshold changed 1→30 in B2).
        res = {"type": "WAREHOUSE", "auto_suspend": "30"}
        assert len(rule.check(res, "WH_DEV")) == 0

    def test_aggressive_auto_suspend_check_non_warehouse_returns_empty(self):
        rule = AggressiveAutoSuspendCheck()
        assert rule.check({"type": "TABLE"}, "t") == []
        assert rule.check({"type": "VIEW"}, "v") == []

    def test_aggressive_auto_suspend_check_with_conventions(self):
        from snowfort_audit.domain.conventions import SnowfortConventions, WarehouseConventions

        conv = SnowfortConventions(warehouse=WarehouseConventions(auto_suspend_seconds=60))
        rule = AggressiveAutoSuspendCheck(conventions=conv)
        assert rule._auto_suspend_limit() == 60
        res = {"type": "WAREHOUSE", "auto_suspend": "120"}
        assert len(rule.check(res, "WH")) == 1
        res = {"type": "WAREHOUSE", "auto_suspend": "30"}
        assert len(rule.check(res, "WH")) == 0  # 30 <= 60
        res = {"type": "WAREHOUSE", "auto_suspend": "1"}
        assert len(rule.check(res, "WH_DEV")) == 0  # at limit

    def test_zombie_warehouse_check(self):
        rule = ZombieWarehouseCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [[("ACTIVE_WH",)], [("ACTIVE_WH", "STARTED"), ("ZOMBIE_WH", "SUSPENDED")]]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "ZOMBIE_WH"

    def test_spillage_detection_check(self):
        rule = RemoteSpillageCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("HEAVY_WH", 10)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1

    def test_local_spillage_check(self):
        rule = LocalSpillageCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("MEDIUM_WH", 3)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Local Spillage" in violations[0].message

    def test_multi_cluster_safeguard_check(self):
        rule = MultiClusterSafeguardCheck()
        res = {"type": "WAREHOUSE", "max_cluster_count": 2, "scaling_policy": "STANDARD"}
        assert len(rule.check(res, "WH_MCW")) == 1
        res_ok = {"type": "WAREHOUSE", "max_cluster_count": 2, "scaling_policy": "ECONOMY"}
        assert len(rule.check(res_ok, "WH_MCW")) == 0

    def test_multi_cluster_safeguard_check_non_warehouse_or_single_cluster(self):
        rule = MultiClusterSafeguardCheck()
        assert rule.check({"type": "DATABASE"}, "db") == []
        assert rule.check({"type": "WAREHOUSE", "max_cluster_count": 1}, "WH") == []
        assert rule.check({"type": "WAREHOUSE"}, "WH") == []

    def test_underutilized_warehouse_check_online(self):
        rule = UnderutilizedWarehouseCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("SMALL_WH", 0.05)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "0.05" in violations[0].message

    def test_high_churn_permanent_table_check_online(self):
        rule = HighChurnPermanentTableCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("DB.SCH.TBL", 1000, 5000)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "DB.SCH.TBL" in violations[0].resource_name

    def test_stale_table_detection_check_online(self):
        rule = StaleTableDetectionCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("DB", "SCH", "OLD_TBL", 150_000_000)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "90" in violations[0].message


class TestPerfRules:
    def test_query_latency_slo_check(self):
        rule = QueryLatencySLOCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("WH1", "SELECT", 2.0, 5.0, 35.0, 1000),
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].rule_id == "PERF_013"
        assert "P99" in violations[0].message

    def test_select_star_check(self):
        mock_validator = MagicMock()
        # Mock validator to return a violation for SELECT *
        mock_violation = MagicMock()
        mock_violation.code = "AM04"
        mock_violation.description = "Query produces unknown or inconsistent number of columns because of SELECT *"
        mock_violation.line = 1
        mock_violation.matches.side_effect = lambda p: p.upper() in mock_violation.description.upper()
        mock_validator.validate.return_value = [mock_violation]

        rule = SelectStarCheck(validator=mock_validator)
        mock_cursor = MagicMock()
        # Mock GET_DDL response
        mock_cursor.fetchone.return_value = ["SELECT * FROM foo"]

        violations = rule.check_online(mock_cursor, _resource_name="MY_VIEW")
        assert len(violations) == 1
        assert "SELECT *" in violations[0].message


class TestReliabilityRules:
    def test_replication_check_gap(self):
        rule = ReplicationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",)]
        mock_cursor.fetchall.side_effect = [
            [("PRD_ANALYTICS",), ("DEV_DB",)],
            [("repl_id", "DEV_DB")],
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "PRD_ANALYTICS" in violations[0].resource_name
        assert "Replication" in violations[0].message

    def test_replication_check_no_prd_returns_empty(self):
        rule = ReplicationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",)]
        mock_cursor.fetchall.side_effect = [[("DEV_DB",), ("STG_DB",)], [("repl_id", "DEV_DB")]]
        assert rule.check_online(mock_cursor) == []

    def test_replication_check_exception_returns_empty(self):
        rule = ReplicationCheck()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("DB error")
        with pytest.raises(RuleExecutionError):
            rule.check_online(mock_cursor)

    def test_retention_safety_check(self):
        rule = RetentionSafetyCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("DB_PRD", "SCHEMA", "TABLE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1

    def test_retention_safety_check_exception_returns_empty(self):
        rule = RetentionSafetyCheck()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("error")
        with pytest.raises(RuleExecutionError):
            rule.check_online(mock_cursor)

    def test_adequate_time_travel_retention_check(self):
        rule = AdequateTimeTravelRetentionCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PRD_DB", "PUBLIC", "CRITICAL_TABLE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "PRD_DB" in violations[0].resource_name
        assert "1-day" in violations[0].message

    def test_adequate_time_travel_retention_check_exception_returns_empty(self):
        rule = AdequateTimeTravelRetentionCheck()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("error")
        with pytest.raises(RuleExecutionError):
            rule.check_online(mock_cursor)

    def test_schema_evolution_check(self):
        rule = SchemaEvolutionCheck()
        res = {"type": "TABLE", "enable_schema_evolution": True}
        assert len(rule.check(res, "EVO_TABLE")) == 1

    def test_schema_evolution_check_online(self):
        rule = SchemaEvolutionCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("DB", "SCHEMA", "EVO_TABLE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "EVO_TABLE" in violations[0].resource_name

    def test_schema_evolution_check_negative(self):
        rule = SchemaEvolutionCheck()
        res = {"type": "TABLE", "enable_schema_evolution": False}
        assert len(rule.check(res, "NORMAL_TABLE")) == 0

    def test_schema_evolution_check_non_table_returns_empty(self):
        rule = SchemaEvolutionCheck()
        assert rule.check({"type": "VIEW"}, "v") == []
        assert rule.check({"type": "DYNAMIC TABLE"}, "dt") == []

    def test_schema_evolution_check_online_error(self):
        rule = SchemaEvolutionCheck()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("DB Error")
        with pytest.raises(RuleExecutionError):
            rule.check_online(mock_cursor)

    def test_aggressive_auto_suspend_check_online(self):
        rule = AggressiveAutoSuspendCheck()
        mock_cursor = MagicMock()

        # 1. Tags query
        # 2. Show warehouses
        mock_cursor.fetchall.side_effect = [
            [("WH_PROD_TAGGED", "PRD")],  # Tags
            [
                ("WH_PROD_TAGGED", 600),
                ("WH_DEV_DEFAULT", 120),
                ("WH_DEV_GOOD", 60),
                ("WH_PRD_NAMED", 300),
            ],
        ]

        # Mock description for column mapping
        mock_cursor.description = [("name",), ("auto_suspend",)]

        violations = rule.check_online(mock_cursor)
        # All 4 exceed Snowfort convention (1s)
        assert len(violations) == 4
        assert any("WH_PROD_TAGGED" in v.resource_name for v in violations)
        assert any("WH_DEV_DEFAULT" in v.resource_name for v in violations)

    def test_aggressive_auto_suspend_check_online_null_suspend_critical(self):
        rule = AggressiveAutoSuspendCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [[], [("WH_NEVER_SUSPENDS", None)]]
        mock_cursor.description = [("name",), ("auto_suspend",)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "WH_NEVER_SUSPENDS"
        assert "NULL" in violations[0].message
        assert violations[0].severity.name == "CRITICAL"

    def test_cloud_services_ratio_check(self):
        rule = CloudServicesRatioCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("WH_INEFFICIENT", 15.5)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "15.5%" in violations[0].message

    def test_cloud_services_ratio_check_exception_returns_empty(self):
        rule = CloudServicesRatioCheck()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("DB unavailable")
        with pytest.raises(RuleExecutionError):
            rule.check_online(mock_cursor)

    def test_runaway_query_check(self):
        rule = RunawayQueryCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("STATEMENT_TIMEOUT_IN_SECONDS", "172800")
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1

    def test_runaway_query_check_pass_when_timeout_acceptable(self):
        rule = RunawayQueryCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("STATEMENT_TIMEOUT_IN_SECONDS", "3600")
        assert rule.check_online(mock_cursor) == []
        mock_cursor.fetchone.return_value = None
        assert rule.check_online(mock_cursor) == []

    def test_underutilized_warehouse_check(self):
        rule = UnderutilizedWarehouseCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("WH_IDLE", 0.05)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1

    def test_per_warehouse_statement_timeout_check(self):
        rule = PerWarehouseStatementTimeoutCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",)]
        # fetchall: SHOW WAREHOUSES, then OBJECT_PARAMETERS overrides
        mock_cursor.fetchall.side_effect = [
            [("WH_DEFAULT",), ("WH_GOOD",)],  # SHOW WAREHOUSES
            [("WH_GOOD", "900")],  # OBJECT_PARAMETERS: WH_GOOD has 900s override
        ]
        # fetchone: SHOW PARAMETERS IN ACCOUNT -> account default = 172800
        mock_cursor.fetchone.return_value = ("STATEMENT_TIMEOUT_IN_SECONDS", "172800", "172800", "SYSTEM", "")
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "WH_DEFAULT"


class TestSecurityRules:
    def test_admin_exposure_check(self):
        rule = AdminExposureCheck()
        mock_cursor = MagicMock()

        # Simulate 4 ACCOUNTADMINs (Fail > 3)
        account_admins = [("role", "grant", "USER", f"User_{i}") for i in range(4)]
        # Simulate 6 SECURITYADMINs (Fail > 5)
        sec_admins = [("role", "grant", "USER", f"User_{i}") for i in range(6)]
        # Simulate 1 SYSADMIN (Pass)
        sys_admins = [("role", "grant", "USER", "User_1")]

        mock_cursor.fetchall.side_effect = [account_admins, sec_admins, sys_admins]

        violations = rule.check_online(mock_cursor)
        # Should have 2 violations: 1 for ACCOUNTADMIN threshold, 1 for SECURITYADMIN threshold
        assert len(violations) == EXPECTED_VIOLATIONS
        assert "Too many ACCOUNTADMINs" in violations[0].message

    def test_network_perimeter_check(self):
        rule = NetworkPerimeterCheck()
        mock_cursor = MagicMock()
        # 1. SHOW PARAMETERS -> ("NETWORK_POLICY", "MY_POLICY")
        # 2. DESCRIBE NETWORK POLICY MY_POLICY -> ALLOWED_IP_LIST="0.0.0.0/0"
        # User-level check is skipped (ACCOUNT_USAGE.USERS does not expose NETWORK_POLICY).

        mock_cursor.fetchone.side_effect = [("NETWORK_POLICY", "MY_POLICY")]
        mock_cursor.fetchall.return_value = [("ALLOWED_IP_LIST", "0.0.0.0/0")]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert any("Internet Open" in v.message for v in violations)

    def test_mfa_enforcement_check(self) -> None:
        rule = MFAEnforcementCheck()
        mock_cursor = MagicMock()

        # Mock cursor description for column mapping
        mock_cursor.description = [
            ("name",),
            ("created_on",),
            ("login_name",),
            ("display_name",),
            ("first_name",),
            ("last_name",),
            ("email",),
            ("mins_to_unlock",),
            ("days_to_expiry",),
            ("comment",),
            ("disabled",),
            ("must_change_password",),
            ("snowflake_lock",),
            ("default_warehouse",),
            ("default_namespace",),
            ("default_role",),
            ("default_secondary_roles",),
            ("ext_authn_duo",),
            ("ext_authn_uid",),
            ("mins_to_bypass_mfa",),
            ("owner",),
            ("last_success_login",),
            ("expires_at_time",),
            ("locked_until_time",),
            ("has_password",),
            ("has_rsa_public_key",),
            ("type",),
            ("has_mfa",),
        ]

        # Helper to create a mock row based on description order
        def make_row(**kwargs) -> tuple:
            row = []
            for col in mock_cursor.description:
                name = col[0]
                val = kwargs.get(name)
                row.append(val)
            return tuple(row)

        # 1. Admin grants (User1 is admin) - Three calls now: AA, SA, SecA
        mock_cursor.fetchall.side_effect = [
            [("role", "grant", "USER", "ADMIN_USER")],  # SHOW GRANTS ACCOUNTADMIN
            [],  # SHOW GRANTS SYSADMIN
            [],  # SHOW GRANTS SECURITYADMIN
            [
                make_row(name="ADMIN_USER", type="PERSON", has_mfa="false", ext_authn_duo="false"),  # Fail
                make_row(name="SERVICE_USER", type="SERVICE", has_mfa="false"),  # Pass (Service)
                make_row(name="SECURE_USER", type="PERSON", has_mfa="true"),  # Pass (MFA)
            ],  # SHOW USERS
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "ADMIN_USER" in violations[0].message
        assert "MFA disabled" in violations[0].message

    def test_service_user_security_check(self) -> None:
        rule = ServiceUserSecurityCheck()
        mock_cursor = MagicMock()

        mock_cursor.description = [("name",), ("type",), ("has_password",), ("has_rsa_public_key",)]

        def make_row(**kwargs) -> tuple:
            return tuple(kwargs.get(col[0], None) for col in mock_cursor.description)

        mock_cursor.fetchall.return_value = [
            make_row(name="BAD_SERVICE", type="SERVICE", has_password="true", has_rsa_public_key="false"),  # 2 Failures
            make_row(name="GOOD_SERVICE", type="SERVICE", has_password="false", has_rsa_public_key="true"),  # Pass
            make_row(name="HUMAN", type="PERSON", has_password="true", has_rsa_public_key="false"),  # Pass (Ignore)
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == EXPECTED_VIOLATIONS
        assert any("BAD_SERVICE" in v.message and "has password" in v.message for v in violations)
        assert any("BAD_SERVICE" in v.message and "missing RSA Key" in v.message for v in violations)

    def test_public_grants_check(self):
        rule = PublicGrantsCheck()
        mock_cursor = MagicMock()
        # [created_on, privilege, granted_on, name, granted_to, grantee_name, grant_option, granted_by]
        mock_cursor.fetchall.return_value = [
            ("date", "USAGE", "DATABASE", "SNOWFLAKE", "ROLE", "PUBLIC", "false", "SYSADMIN"),  # Pass
            ("date", "MODIFY", "TABLE", "DB.SCHEMA.TABLE", "ROLE", "PUBLIC", "false", "SYSADMIN"),  # Fail
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Excessive privilege 'MODIFY'" in violations[0].message

    def test_user_ownership_check(self):
        UserOwnershipCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("owner",)]

        # 1. Databases
        # 2. Warehouses
        # 3. Integrations
        mock_cursor.fetchall.side_effect = [
            [("BAD_DB", "USER_JOE")],  # Fail
            [("GOOD_WH", "SYSADMIN")],  # Pass
            [],  # Integrations
        ]

    def test_zombie_user_check(self):
        rule = ZombieUserCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("last_success_login",), ("created_on",)]

        now = datetime.now()
        old = now - timedelta(days=100)
        recent = now - timedelta(days=10)

        mock_cursor.fetchall.return_value = [
            ("ZOMBIE", old, old),  # Fail (inactive > 90)
            ("ACTIVE", recent, old),  # Pass
            ("NEW_GHOST", None, old),  # Fail (Created > 30, never logged in)
            ("NEW_USER", None, now),  # Pass (Created recently)
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == EXPECTED_VIOLATIONS
        assert any("ZOMBIE" in v.resource_name for v in violations)
        assert any("NEW_GHOST" in v.resource_name for v in violations)

    def test_zombie_role_check(self):
        rule = ZombieRoleCheck()
        mock_cursor = MagicMock()

        # Batch approach: 1. SHOW ROLES, 2. GRANTS_TO_ROLES (granted_on='ROLE'),
        # 3. GRANTS_TO_USERS, 4. GRANTS_TO_ROLES (grantee set)
        # ROLE_ORPHAN: not in non_orphan_roles -> Orphan; IS in roles_with_grants -> not Empty
        # ROLE_EMPTY:  IS in non_orphan_roles  -> not Orphan; not in roles_with_grants -> Empty
        # ROLE_GOOD:   IS in non_orphan_roles  -> not Orphan; IS in roles_with_grants -> not Empty
        mock_cursor.fetchall.side_effect = [
            [("row", "ROLE_ORPHAN"), ("row", "ROLE_EMPTY"), ("row", "ROLE_GOOD")],  # SHOW ROLES
            [("ROLE_EMPTY",), ("ROLE_GOOD",)],  # GRANTS_TO_ROLES granted_on='ROLE' -> non-orphan
            [],  # GRANTS_TO_USERS -> no additions
            [("ROLE_ORPHAN",), ("ROLE_GOOD",)],  # GRANTS_TO_ROLES grantee_name -> has grants
        ]

        violations = rule.check_online(mock_cursor)
        assert len(violations) == EXPECTED_VIOLATIONS
        assert any("ROLE_ORPHAN" in v.resource_name and "Orphan" in v.message for v in violations)
        assert any("ROLE_EMPTY" in v.resource_name and "Empty" in v.message for v in violations)

    def test_federated_authentication_check(self):
        rule = FederatedAuthenticationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("name",),
            ("has_password",),
            ("ext_authn_duo",),
            ("has_rsa_public_key",),
            ("type",),
        ]
        # User with password, no MFA/SSO/key -> violation
        mock_cursor.fetchall.return_value = [
            ("PWD_ONLY_USER", "true", "false", "false", "PERSON"),
            ("SSO_USER", "true", "true", "false", "PERSON"),
            ("SVC_USER", "true", "false", "true", "SERVICE"),
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "PWD_ONLY_USER" in violations[0].message

    def test_password_policy_check(self):
        rule = PasswordPolicyCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "No password policy" in violations[0].message

    def test_password_policy_check_pass(self):
        rule = PasswordPolicyCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("POLICY_1",)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_data_exfiltration_prevention_check(self):
        rule = DataExfiltrationPreventionCheck()
        mock_cursor = MagicMock()
        # First param OK, second param wrong
        mock_cursor.fetchone.side_effect = [
            ("key", "TRUE", "default", "level", "desc"),
            ("key", "FALSE", "default", "level", "desc"),
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Stage creation" in violations[0].message or "storage integration" in violations[0].message.lower()

    def test_private_connectivity_check(self):
        rule = PrivateConnectivityCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("key", "value")
        mock_cursor.fetchall.return_value = []
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "No network policy" in violations[0].message

    def test_sso_coverage_check(self):
        rule = SSOCoverageCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("SSO_USER", "sso@co", "ext_123"),
            ("LOCAL_USER", "local@co", None),
            ("OTHER_SSO", "o@co", "ext_456"),
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert violations[0].resource_name == "LOCAL_USER"
        assert "SSO" in violations[0].message


class TestOpExcellenceRules:
    def test_resource_monitor_check(self):
        rule = ResourceMonitorCheck()
        mock_cursor = MagicMock()
        # Mock monitors and warehouses
        mock_cursor.fetchall.side_effect = [
            [],  # SHOW RESOURCE MONITORS
            [
                (
                    "WH_1",
                    "STARTED",
                    "XSMALL",
                    1,
                    1,
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                    "null",
                )
            ],  # SHOW WAREHOUSES
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) >= 1

    def test_object_comment_check(self):
        rule = ObjectCommentCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("ID", "MY_DB", "CREATED", "MODIFIED", "UNUSED", "OWNER", "TYPE", "RETENTION", "KIND", "")
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1

    def test_alert_configuration_check_no_alerts(self):
        rule = AlertConfigurationCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "No Snowflake Alerts" in violations[0].message

    def test_alert_configuration_check_none_resumed(self):
        rule = AlertConfigurationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("state",)]
        mock_cursor.fetchall.return_value = [("ALERT_1", "suspended"), ("ALERT_2", "suspended")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "none are RESUMED" in violations[0].message

    def test_alert_configuration_check_pass(self):
        rule = AlertConfigurationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("state",)]
        mock_cursor.fetchall.return_value = [("ALERT_1", "started")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_notification_integration_check(self):
        rule = NotificationIntegrationCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "No notification integration" in violations[0].message

    def test_observability_infrastructure_check(self):
        rule = ObservabilityInfrastructureCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("id", "MY_DB"), ("id", "OTHER_DB")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "observability" in violations[0].message.lower()

    def test_observability_infrastructure_check_pass(self):
        rule = ObservabilityInfrastructureCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("id", "OBSERVABILITY_DB")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_iac_drift_readiness_check(self):
        rule = IaCDriftReadinessCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],  # TAG_REFERENCES: no managed-by tags
            [("wh1",)],  # SHOW WAREHOUSES
            [("id", "WH1"), ("id", "SNOWFLAKE")],  # SHOW DATABASES
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) >= 1
        assert any("warehouse" in v.message.lower() for v in violations)

    def test_iac_drift_readiness_check_pass(self):
        rule = IaCDriftReadinessCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [("WAREHOUSE", "WH1", "MANAGED_BY"), ("DATABASE", "DB1", "TERRAFORM")],
            [("wh1",)],
            [("id", "DB1"), ("id", "SNOWFLAKE")],
        ]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_event_table_configuration_check_no_customer_owned(self):
        rule = EventTableConfigurationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("owner",)]
        mock_cursor.fetchall.return_value = [("evt_1", "SNOWFLAKE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "event table" in violations[0].message.lower()

    def test_event_table_configuration_check_pass(self):
        rule = EventTableConfigurationCheck()
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("owner",)]
        mock_cursor.fetchall.return_value = [("my_events", "MY_ROLE")]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_data_metric_functions_coverage_check_no_dmf(self):
        rule = DataMetricFunctionsCoverageCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "Data Metric" in violations[0].message

    def test_data_metric_functions_coverage_check_pass(self):
        rule = DataMetricFunctionsCoverageCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0

    def test_alert_execution_reliability_check_low_success_rate(self):
        rule = AlertExecutionReliabilityCheck()
        mock_cursor = MagicMock()
        # OPS_012 queries ALERT_HISTORY; rows are (NAME, DATABASE_NAME, SCHEMA_NAME, STATE, err_count, total_runs)
        mock_cursor.fetchall.return_value = [("MY_ALERT", "DB", "SCHEMA", "started", 5, 10)]
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 1
        assert "error" in violations[0].message.lower()
        assert "5" in violations[0].message

    def test_alert_execution_reliability_check_pass(self):
        rule = AlertExecutionReliabilityCheck()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (100, 2)
        violations = rule.check_online(mock_cursor)
        assert len(violations) == 0


class TestStaticRules:
    def test_hardcoded_env_check(self):
        rule = HardcodedEnvCheck()
        assert len(rule.check_static("SELECT * FROM DB_PROD.SCHEMA.TABLE", "query.sql")) == 1

    def test_naked_drop_check(self):
        rule = NakedDropCheck()
        assert len(rule.check_static("DROP TABLE FOO", "query.sql")) == 1

    def test_secret_exposure_check(self):
        rule = SecretExposureCheck()
        assert len(rule.check_static('password: "my_secret_pwd"', "config.yaml")) == 1
