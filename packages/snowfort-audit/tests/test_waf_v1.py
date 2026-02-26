from unittest.mock import MagicMock

from snowfort_audit.domain.rules.cost import UnderutilizedWarehouseCheck
from snowfort_audit.domain.rules.op_excellence import MandatoryTaggingCheck
from snowfort_audit.domain.rules.reliability import ReplicationCheck
from snowfort_audit.domain.rules.security import MFAEnforcementCheck, ZombieRoleCheck


def test_sec_002_mfa_enforcement():
    """Test SEC_002 flags admins without MFA."""
    expected_violations_mfa = 1
    rule = MFAEnforcementCheck()
    mock_cursor = MagicMock()

    # 1. Grants: user1 has ACCOUNTADMIN
    mock_cursor.execute.side_effect = None  # Reset

    # We need to structure the side_effects to return sequence of results for multiple executes
    # Calls:
    # 1. SHOW GRANTS OF ROLE ACCOUNTADMIN
    # 2. SHOW GRANTS OF ROLE SYSADMIN
    # 3. SHOW GRANTS OF ROLE SECURITYADMIN
    # 4. SHOW USERS

    rows_accountadmin: list = [("date", "role", "USER", "user1")]
    rows_sysadmin: list = []
    rows_securityadmin: list = []

    # Mocking rows: created_on, name, login_name...
    # Logic uses cols description mapping.
    # Description: [('name',..), ('type',..), ('ext_authn_duo',..)]

    mock_cursor.fetchall.side_effect = [
        rows_accountadmin,  # AA
        rows_sysadmin,  # SA
        rows_securityadmin,  # SecA
        [
            # user1: No MFA -> Violation
            ("user1", "PERSON", "false", None, None),
            # user2: Has MFA -> OK (not an admin anyway)
            ("user2", "PERSON", "true", None, None),
            # user3: Service User -> OK (Skipped)
            ("user3", "SERVICE", "false", None, None),
        ],
    ]

    # Mock Description for SHOW USERS (Call 4)
    # Note: previous calls also check description? No, usually just fetchall for grants.
    # Wait, detailed logic might rely on implicit state.
    # Let's mock descriptions appropriately.

    # The rule calls description ONLY after SHOW USERS
    mock_cursor.description = [
        ("name", "str"),
        ("type", "str"),
        ("ext_authn_duo", "str"),
        ("last_success_login", "date"),
        ("created_on", "date"),
    ]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == expected_violations_mfa
    assert violations[0].resource_name == "User"
    assert "user1" in violations[0].message
    assert "MFA disabled" in violations[0].message


def test_ops_001_tagging_logic():
    """Test OPS_001 differentiates between Missing Tags (Error) and Missing Standard Tags (Warning)."""
    expected_violations_tagging = 2
    rule = MandatoryTaggingCheck()
    mock_cursor = MagicMock()

    # Calls:
    # 1. SHOW WAREHOUSES
    # 2. SHOW DATABASES
    # 3. SELECT ... TAG_REFERENCES

    mock_cursor.fetchall.side_effect = [
        [("WH_NO_TAGS",)],  # Warehouses
        [("date", "DB_PARTIAL_TAGS")],  # Databases (Tuples need index 1)
        [
            # Tag Refs: (DOMAIN, NAME, TAG_NAME)
            ("DATABASE", "DB_PARTIAL_TAGS", "COST_CENTER")
            # DB_PARTIAL_TAGS has COST_CENTER, but missing OWNER/ENV
        ],
    ]

    violations = rule.check_online(mock_cursor)

    # Expected:
    # WH_NO_TAGS -> Critical (0 tags)
    # DB_PARTIAL_TAGS -> Medium (Missing recommended)

    assert len(violations) == expected_violations_tagging

    v_wh = next(v for v in violations if "WH_NO_TAGS" in v.resource_name)
    assert v_wh.severity.name == "CRITICAL"  # High/Critical
    assert "ZERO tags" in v_wh.message

    v_db = next(v for v in violations if "DB_PARTIAL_TAGS" in v.resource_name)
    assert v_db.severity.name == "MEDIUM"
    assert "Missing recommended" in v_db.message
    assert "OWNER" in v_db.message


def test_sec_008_zombie_roles():
    """Test SEC_008 flags Orphan and Empty roles."""
    expected_violations_roles = 2
    rule = ZombieRoleCheck()
    mock_cursor = MagicMock()

    # Calls:
    # 1. SHOW ROLES -> ['R_ORPHAN', 'R_EMPTY', 'R_OK']
    # Loop R_ORPHAN:
    #   2. SHOW GRANTS OF ROLE R_ORPHAN -> [] (No one has it) -> ORPHAN
    #   3. SHOW GRANTS TO ROLE R_ORPHAN -> ['usage'] (It has privs)
    # Loop R_EMPTY:
    #   4. SHOW GRANTS OF ROLE R_EMPTY -> ['user'] (Someone has it)
    #   5. SHOW GRANTS TO ROLE R_EMPTY -> [] (Has no privs) -> EMPTY
    # Loop R_OK:
    #   6. SHOW GRANTS OF ROLE R_OK -> ['user']
    #   7. SHOW GRANTS TO ROLE R_OK -> ['usage']

    mock_cursor.fetchall.side_effect = [
        [(None, "R_ORPHAN"), (None, "R_EMPTY"), (None, "R_OK")],  # SHOW ROLES (row[1] is name)
        [],  # R_ORPHAN Grants OF (Empty -> Orphan)
        [("priv",)],  # R_ORPHAN Grants TO (Has privs)
        [("user",)],  # R_EMPTY Grants OF (Has user)
        [],  # R_EMPTY Grants TO (Empty -> Empty)
        [("user",)],  # R_OK Grants OF
        [("priv",)],  # R_OK Grants TO
    ]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == expected_violations_roles

    v_orphan = next(v for v in violations if v.resource_name == "R_ORPHAN")
    assert "Orphan" in v_orphan.message

    v_empty = next(v for v in violations if v.resource_name == "R_EMPTY")
    assert "Empty" in v_empty.message


def test_rel_001_replication():
    """Test REL_001 flags PRD databases not in replication list."""
    rule = ReplicationCheck()
    mock_cursor = MagicMock()

    # Calls:
    # 1. SHOW DATABASES (Description needed for column map)
    # 2. SHOW REPLICATION DATABASES

    mock_cursor.description = [("created", "date"), ("name", "str")]
    mock_cursor.fetchall.side_effect = [
        [("date", "PRD_DB"), ("date", "DEV_DB")],  # DBs
        [("uuid", "DEV_DB")],  # Replicated List (PRD is missing!)
    ]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == 1
    assert violations[0].resource_name == "Database 'PRD_DB'"


def test_cost_006_underutilized():
    """Test COST_006 flags low load warehouses."""
    rule = UnderutilizedWarehouseCheck()
    mock_cursor = MagicMock()

    # Calls:
    # 1. QUERY WAREHOUSE_LOAD_HISTORY

    mock_cursor.fetchall.return_value = [
        # ('WH_BUSY', 0.5), # SQL Filter removes this
        ("WH_IDLE", 0.05)  # SQL Filter allows this
    ]

    violations = rule.check_online(mock_cursor)

    assert len(violations) == 1
    assert violations[0].resource_name == "WH_IDLE"
    assert "Consider down-sizing" in violations[0].message
