"""Tests for security rules."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from snowfort_audit.domain.rules.security import (
    AdminExposureCheck,
    CISBenchmarkScannerCheck,
    DataExfiltrationPreventionCheck,
    DataMaskingPolicyCoverageCheck,
    FederatedAuthenticationCheck,
    MFAAccountEnforcementCheck,
    MFAEnforcementCheck,
    NetworkPerimeterCheck,
    PasswordPolicyCheck,
    PrivateConnectivityCheck,
    PublicGrantsCheck,
    RowAccessPolicyCoverageCheck,
    ServiceUserSecurityCheck,
    SSOCoverageCheck,
    UserOwnershipCheck,
    ZombieRoleCheck,
    ZombieUserCheck,
)
from snowfort_audit.domain.rules.security_advanced import (
    ReadOnlyRoleIntegrityCheck,
    ReadOnlyUserIntegrityCheck,
    ServiceRoleScopeCheck,
    ServiceUserScopeCheck,
)


def test_admin_too_many():
    assert len(AdminExposureCheck()._check_account_admin(5)) == 1


def test_admin_too_few():
    assert len(AdminExposureCheck()._check_account_admin(1)) == 1


def test_admin_ok():
    assert AdminExposureCheck()._check_account_admin(2) == []


def test_admin_generic():
    assert len(AdminExposureCheck()._check_generic_admin("SEC", 6)) == 1
    assert AdminExposureCheck()._check_generic_admin("SYS", 3) == []


def test_mfa_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert MFAEnforcementCheck().check_online(c) == []


def test_network_no_policy():
    c = MagicMock()
    c.fetchone.return_value = ("NP", "")
    assert len(NetworkPerimeterCheck()._check_account(c)) == 1


def test_network_open_ip():
    c = MagicMock()
    c.fetchone.side_effect = [("NP", "pol"), None]
    c.fetchall.return_value = [("ALLOWED_IP_LIST", "0.0.0.0/0")]
    assert len(NetworkPerimeterCheck()._check_account(c)) == 1


def test_network_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert NetworkPerimeterCheck()._check_account(c) == []


def test_public_grants():
    c = MagicMock()
    c.fetchall.return_value = [("cr", "SELECT", "TABLE", "MY.PUB.T")]
    assert len(PublicGrantsCheck().check_online(c)) == 1


def test_public_grants_system():
    c = MagicMock()
    c.fetchall.return_value = [("cr", "SELECT", "TABLE", "SNOWFLAKE.AU.T")]
    assert PublicGrantsCheck().check_online(c) == []


def test_user_ownership():
    c = MagicMock()
    c.description = [("name",), ("owner",)]
    c.fetchall.side_effect = [[("DB", "JOHN")], [], []]
    assert len(UserOwnershipCheck().check_online(c)) == 1


def test_user_ownership_role():
    c = MagicMock()
    c.description = [("name",), ("owner",)]
    c.fetchall.side_effect = [[("DB", "SYSADMIN")], [], []]
    assert UserOwnershipCheck().check_online(c) == []


def test_svc_pwd():
    c = MagicMock()
    c.description = [("name",), ("type",), ("has_password",), ("has_rsa_public_key",)]
    c.fetchall.return_value = [("SVC", "SERVICE", "true", "true")]
    assert len(ServiceUserSecurityCheck().check_online(c)) == 1


def test_svc_no_key():
    c = MagicMock()
    c.description = [("name",), ("type",), ("has_password",), ("has_rsa_public_key",)]
    c.fetchall.return_value = [("SVC", "SERVICE", "false", "false")]
    assert len(ServiceUserSecurityCheck().check_online(c)) == 1


def test_svc_no_type():
    c = MagicMock()
    c.description = [("name",), ("has_password",)]
    assert ServiceUserSecurityCheck().check_online(c) == []


def test_zombie_user():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [
        ("U", datetime.now(timezone.utc) - timedelta(days=120), datetime.now(timezone.utc) - timedelta(days=200))
    ]
    assert len(ZombieUserCheck().check_online(c)) == 1


def test_zombie_user_never():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [("U", None, datetime.now(timezone.utc) - timedelta(days=60))]
    assert len(ZombieUserCheck().check_online(c)) == 1


def test_zombie_user_ok():
    c = MagicMock()
    c.description = [("name",), ("last_success_login",), ("created_on",)]
    c.fetchall.return_value = [("U", None, datetime.now(timezone.utc) - timedelta(days=5))]
    assert ZombieUserCheck().check_online(c) == []


def test_zombie_role():
    c = MagicMock()
    # SHOW ROLES -> CUSTOM; GRANTS_TO_ROLES(granted_on='ROLE') -> []; GRANTS_TO_USERS -> [];
    # GRANTS_TO_ROLES(grantee) -> [] => CUSTOM is Orphan + Empty = 2 violations
    c.fetchall.side_effect = [[("cr", "CUSTOM")], [], [], []]
    assert len(ZombieRoleCheck().check_online(c)) == 2


def test_zombie_role_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert ZombieRoleCheck().check_online(c) == []


def test_federated_pwd():
    c = MagicMock()
    c.description = [
        ("name",),
        ("has_password",),
        ("has_mfa",),
        ("ext_authn_duo",),
        ("has_rsa_public_key",),
        ("ext_authn_uid",),
        ("type",),
    ]
    c.fetchall.return_value = [("U", "true", "false", "false", "false", "", "PERSON")]
    assert len(FederatedAuthenticationCheck().check_online(c)) == 1


def test_federated_svc():
    c = MagicMock()
    c.description = [
        ("name",),
        ("has_password",),
        ("has_mfa",),
        ("ext_authn_duo",),
        ("has_rsa_public_key",),
        ("ext_authn_uid",),
        ("type",),
    ]
    c.fetchall.return_value = [("SVC", "true", "false", "false", "false", "", "SERVICE")]
    assert FederatedAuthenticationCheck().check_online(c) == []


def test_mfa_acct_none():
    c = MagicMock()
    c.fetchone.return_value = None
    assert len(MFAAccountEnforcementCheck().check_online(c)) == 1


def test_mfa_acct_false():
    c = MagicMock()
    c.fetchone.return_value = ("k", "FALSE")
    assert len(MFAAccountEnforcementCheck().check_online(c)) == 1


def test_mfa_acct_true():
    c = MagicMock()
    c.fetchone.return_value = ("k", "TRUE")
    assert MFAAccountEnforcementCheck().check_online(c) == []


def test_mfa_acct_exc():
    c = MagicMock()
    c.execute.side_effect = RuntimeError()
    assert MFAAccountEnforcementCheck().check_online(c) == []


def test_cis_found():
    c = MagicMock()
    c.fetchall.return_value = [("CIS Snowflake Benchmark", "ENABLED")]
    assert CISBenchmarkScannerCheck().check_online(c) == []


def test_cis_not_found():
    c = MagicMock()
    c.fetchall.return_value = [("Other", "X")]
    assert len(CISBenchmarkScannerCheck().check_online(c)) == 1


def test_pwd_policy_none():
    c = MagicMock()
    c.fetchall.return_value = []
    assert len(PasswordPolicyCheck().check_online(c)) == 1


def test_pwd_policy_ok():
    c = MagicMock()
    c.fetchall.return_value = [("p",)]
    assert PasswordPolicyCheck().check_online(c) == []


def test_exfil_not_set():
    c = MagicMock()
    c.fetchone.side_effect = [("k", "FALSE"), ("k", "FALSE")]
    assert len(DataExfiltrationPreventionCheck().check_online(c)) == 2


def test_exfil_ok():
    c = MagicMock()
    c.fetchone.side_effect = [("k", "TRUE"), ("k", "TRUE")]
    assert DataExfiltrationPreventionCheck().check_online(c) == []


def test_priv_conn_no():
    c = MagicMock()
    c.fetchone.return_value = ("k", "4")
    c.fetchall.return_value = []
    assert len(PrivateConnectivityCheck().check_online(c)) == 1


def test_priv_conn_ok():
    c = MagicMock()
    c.fetchone.return_value = ("k", "4")
    c.fetchall.return_value = [("p",)]
    assert PrivateConnectivityCheck().check_online(c) == []


def test_masking():
    c = MagicMock()
    c.fetchall.return_value = [("DB.S.T", "EMAIL", "PII")]
    assert len(DataMaskingPolicyCoverageCheck().check_online(c)) == 1


def test_rap():
    c = MagicMock()
    c.fetchall.return_value = [("DB.S.T",)]
    assert len(RowAccessPolicyCoverageCheck().check_online(c)) == 1


def test_sso():
    c = MagicMock()
    c.fetchall.return_value = [("S1", "s", "ext"), ("S2", "s", "ext"), ("N", "n", "")]
    assert len(SSOCoverageCheck().check_online(c)) == 1


def test_sso_empty():
    c = MagicMock()
    c.fetchall.return_value = []
    assert SSOCoverageCheck().check_online(c) == []


def test_adv_svc_role():
    c = MagicMock()
    c.fetchall.return_value = [("SVC_M", 3)]
    assert len(ServiceRoleScopeCheck().check_online(c)) == 1


def test_adv_svc_user():
    c = MagicMock()
    c.fetchall.return_value = [("SVC_M", 2)]
    assert len(ServiceUserScopeCheck().check_online(c)) == 1


def test_adv_ro_role():
    c = MagicMock()
    c.fetchall.return_value = [("A_RO", "INSERT", "TABLE", "T")]
    assert len(ReadOnlyRoleIntegrityCheck().check_online(c)) == 1


def test_adv_ro_user():
    c = MagicMock()
    c.fetchall.return_value = [("R_READER", "DELETE", "TABLE", "T")]
    assert len(ReadOnlyUserIntegrityCheck().check_online(c)) == 1
