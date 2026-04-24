import contextlib
import importlib.util
import inspect
import sys
from importlib.metadata import entry_points
from pathlib import Path

from snowfort_audit.domain.financials import FinancialEvaluator
from snowfort_audit.domain.protocols import TelemetryPort
from snowfort_audit.domain.rule_definitions import Rule
from snowfort_audit.domain.rules import (
    AccountBudgetEnforcement,
    AdequateTimeTravelRetentionCheck,
    AdminExposureCheck,
    AggressiveAutoSuspendCheck,
    AIRedactPolicyCoverageCheck,
    AlertConfigurationCheck,
    AlertExecutionReliabilityCheck,
    AntiPatternSQLDetectionCheck,
    AuthorizationPolicyCheck,
    AutomaticClusteringCostBenefitCheck,
    CacheContentionCheck,
    CISBenchmarkScannerCheck,
    CloudServicesRatioCheck,
    ClusteringKeyQualityCheck,
    ClusterKeyValidationCheck,
    CrossRegionInferenceCheck,
    DataExfiltrationPreventionCheck,
    DataMaskingPolicyCoverageCheck,
    DataMetricFunctionsCoverageCheck,
    DataTransferMonitoringCheck,
    DeveloperSandboxSprawlCheck,
    DynamicTableComplexityCheck,
    DynamicTableFailureDetectionCheck,
    DynamicTableLagCheck,
    DynamicTableRefreshLagCheck,
    EventTableConfigurationCheck,
    FailedTaskDetectionCheck,
    FailoverGroupCompletenessCheck,
    FederatedAuthenticationCheck,
    FutureGrantsAntiPatternCheck,
    Gen2UpgradeCheck,
    HardcodedEnvCheck,
    HighChurnPermanentTableCheck,
    IaCDriftReadinessCheck,
    IcebergTableGovernanceCheck,
    InboundShareRiskCheck,
    IsolationPivotCheck,
    LocalSpillageCheck,
    MandatoryTaggingCheck,
    MaskingPolicyCoverageExtendedCheck,
    MergePatternRecommendationCheck,
    MFAAccountEnforcementCheck,
    MFAEnforcementCheck,
    MultiClusterSafeguardCheck,
    NakedDropCheck,
    NetworkPerimeterCheck,
    NotificationIntegrationCheck,
    ObjectCommentCheck,
    ObjectDocumentationCheck,
    ObservabilityInfrastructureCheck,
    OutboundShareRiskCheck,
    PasswordPolicyCheck,
    PermifrostDriftCheck,
    PerWarehouseStatementTimeoutCheck,
    PipelineObjectReplicationCheck,
    PoorPartitionPruningDetectionCheck,
    PrivateConnectivityCheck,
    PrivateLinkOnlyEnforcementCheck,
    ProgrammaticAccessTokenCheck,
    PublicGrantsCheck,
    QASEligibilityRecommendationCheck,
    QueryLatencySLOCheck,
    QueryQueuingDetectionCheck,
    ReadOnlyRoleIntegrityCheck,
    ReadOnlyUserIntegrityCheck,
    RemoteSpillageCheck,
    ReplicationCheck,
    ReplicationLagMonitoringCheck,
    ResizeChurnCheck,
    ResourceMonitorCheck,
    RetentionSafetyCheck,
    RowAccessPolicyCoverageCheck,
    RunawayQueryCheck,
    SchemaEvolutionCheck,
    SearchOptimizationCostBenefitCheck,
    SecretExposureCheck,
    SelectStarCheck,
    SensitiveDataClassificationCoverageCheck,
    ServiceRoleScopeCheck,
    ServiceUserScopeCheck,
    ServiceUserSecurityCheck,
    SLOThrottlerCheck,
    SnowparkContainerServicesSecurityCheck,
    SnowparkOptimizationCheck,
    SpillingMemoryCheck,
    SSOCoverageCheck,
    StagingTableTypeOptimizationCheck,
    StaleTableDetectionCheck,
    TrustCenterExtensionsCheck,
    UnderutilizedWarehouseCheck,
    UnusedMaterializedViewCheck,
    UserOwnershipCheck,
    WarehouseWorkloadIsolationCheck,
    WorkloadEfficiencyCheck,
    WorkloadHeterogeneityCheck,
    ZombieRoleCheck,
    ZombieUserCheck,
    ZombieWarehouseCheck,
)
from snowfort_audit.domain.rules.cortex_cost import get_cortex_rules
from snowfort_audit.domain.rules.sizing import (
    DormantWarehouseCheck,
    ExcessiveTimeTravelRetentionCheck,
    ThreeLayerUtilizationCheck,
)
from snowfort_audit.infrastructure.config_loader import load_conventions
from snowfort_audit.infrastructure.gateways.sql_validator import SqlFluffValidatorGateway


def get_all_rules(
    evaluator: FinancialEvaluator,
    telemetry: TelemetryPort | None = None,
    project_root: Path | None = None,
    permifrost_spec_path: str | None = None,
) -> list[Rule]:
    """Returns all audit rules with injected dependencies."""
    validator = SqlFluffValidatorGateway()
    conventions = load_conventions(project_root or Path.cwd())

    return [
        # Cost
        AggressiveAutoSuspendCheck(conventions=conventions, telemetry=telemetry),
        ZombieWarehouseCheck(telemetry=telemetry),
        CloudServicesRatioCheck(telemetry=telemetry),
        RunawayQueryCheck(telemetry=telemetry),
        MultiClusterSafeguardCheck(telemetry=telemetry),
        WorkloadHeterogeneityCheck(telemetry=telemetry),
        HighChurnPermanentTableCheck(conventions=conventions, telemetry=telemetry),
        UnderutilizedWarehouseCheck(telemetry=telemetry),
        IsolationPivotCheck(telemetry=telemetry),
        PerWarehouseStatementTimeoutCheck(telemetry=telemetry),
        StaleTableDetectionCheck(telemetry=telemetry),
        StagingTableTypeOptimizationCheck(telemetry=telemetry),
        UnusedMaterializedViewCheck(telemetry=telemetry),
        DataTransferMonitoringCheck(telemetry=telemetry),
        QASEligibilityRecommendationCheck(telemetry=telemetry),
        AutomaticClusteringCostBenefitCheck(telemetry=telemetry),
        SearchOptimizationCostBenefitCheck(telemetry=telemetry),
        # Security
        AdminExposureCheck(telemetry=telemetry),
        CISBenchmarkScannerCheck(telemetry=telemetry),
        DataMaskingPolicyCoverageCheck(telemetry=telemetry),
        RowAccessPolicyCoverageCheck(telemetry=telemetry),
        MFAEnforcementCheck(telemetry=telemetry),
        NetworkPerimeterCheck(telemetry=telemetry),
        PublicGrantsCheck(telemetry=telemetry),
        UserOwnershipCheck(telemetry=telemetry),
        ServiceUserSecurityCheck(telemetry=telemetry),
        ZombieUserCheck(telemetry=telemetry),
        ZombieRoleCheck(telemetry=telemetry),
        ServiceRoleScopeCheck(telemetry=telemetry),
        ServiceUserScopeCheck(telemetry=telemetry),
        ReadOnlyRoleIntegrityCheck(telemetry=telemetry),
        ReadOnlyUserIntegrityCheck(telemetry=telemetry),
        FederatedAuthenticationCheck(telemetry=telemetry),
        MFAAccountEnforcementCheck(telemetry=telemetry),
        PasswordPolicyCheck(telemetry=telemetry),
        DataExfiltrationPreventionCheck(telemetry=telemetry),
        PrivateConnectivityCheck(telemetry=telemetry),
        SSOCoverageCheck(telemetry=telemetry),
        ProgrammaticAccessTokenCheck(telemetry=telemetry),
        AIRedactPolicyCoverageCheck(telemetry=telemetry),
        AuthorizationPolicyCheck(telemetry=telemetry),
        TrustCenterExtensionsCheck(telemetry=telemetry),
        PrivateLinkOnlyEnforcementCheck(telemetry=telemetry),
        SnowparkContainerServicesSecurityCheck(telemetry=telemetry),
        # Performance
        ClusterKeyValidationCheck(telemetry=telemetry),
        SchemaEvolutionCheck(telemetry=telemetry),
        LocalSpillageCheck(telemetry=telemetry),
        RemoteSpillageCheck(telemetry=telemetry),
        WorkloadEfficiencyCheck(evaluator, telemetry=telemetry),
        SpillingMemoryCheck(evaluator, telemetry=telemetry),
        Gen2UpgradeCheck(telemetry=telemetry),
        SnowparkOptimizationCheck(telemetry=telemetry),
        CacheContentionCheck(telemetry=telemetry),
        QueryQueuingDetectionCheck(telemetry=telemetry),
        DynamicTableLagCheck(telemetry=telemetry),
        ClusteringKeyQualityCheck(telemetry=telemetry),
        WarehouseWorkloadIsolationCheck(telemetry=telemetry),
        PoorPartitionPruningDetectionCheck(telemetry=telemetry),
        QueryLatencySLOCheck(telemetry=telemetry),
        # Ops
        SLOThrottlerCheck(evaluator, telemetry=telemetry),
        ResizeChurnCheck(telemetry=telemetry),
        ResourceMonitorCheck(telemetry=telemetry),
        ObjectCommentCheck(telemetry=telemetry),
        MandatoryTaggingCheck(conventions=conventions, telemetry=telemetry),
        AlertConfigurationCheck(telemetry=telemetry),
        AlertExecutionReliabilityCheck(telemetry=telemetry),
        NotificationIntegrationCheck(telemetry=telemetry),
        ObservabilityInfrastructureCheck(telemetry=telemetry),
        IaCDriftReadinessCheck(telemetry=telemetry),
        EventTableConfigurationCheck(telemetry=telemetry),
        DataMetricFunctionsCoverageCheck(telemetry=telemetry),
        DeveloperSandboxSprawlCheck(telemetry=telemetry),
        PermifrostDriftCheck(spec_path=permifrost_spec_path, telemetry=telemetry),
        # Governance
        AccountBudgetEnforcement(telemetry=telemetry),
        FutureGrantsAntiPatternCheck(telemetry=telemetry),
        ObjectDocumentationCheck(telemetry=telemetry),
        SensitiveDataClassificationCoverageCheck(telemetry=telemetry),
        MaskingPolicyCoverageExtendedCheck(telemetry=telemetry),
        InboundShareRiskCheck(telemetry=telemetry),
        OutboundShareRiskCheck(telemetry=telemetry),
        CrossRegionInferenceCheck(telemetry=telemetry),
        IcebergTableGovernanceCheck(telemetry=telemetry),
        # Reliability
        ReplicationCheck(telemetry=telemetry),
        RetentionSafetyCheck(telemetry=telemetry),
        AdequateTimeTravelRetentionCheck(telemetry=telemetry),
        FailoverGroupCompletenessCheck(telemetry=telemetry),
        ReplicationLagMonitoringCheck(telemetry=telemetry),
        FailedTaskDetectionCheck(telemetry=telemetry),
        PipelineObjectReplicationCheck(telemetry=telemetry),
        DynamicTableRefreshLagCheck(telemetry=telemetry),
        DynamicTableFailureDetectionCheck(telemetry=telemetry),
        # Static
        HardcodedEnvCheck(telemetry=telemetry),
        NakedDropCheck(telemetry=telemetry),
        SecretExposureCheck(telemetry=telemetry),
        SelectStarCheck(validator, telemetry=telemetry),
        MergePatternRecommendationCheck(telemetry=telemetry),
        DynamicTableComplexityCheck(telemetry=telemetry),
        AntiPatternSQLDetectionCheck(telemetry=telemetry),
        # Cortex cost governance (D1–D6, COST_016–033)
        *get_cortex_rules(conventions=conventions, telemetry=telemetry),
        # Directive B — warehouse sizing + storage (pilot rules; remaining rules in follow-ups)
        ThreeLayerUtilizationCheck(conventions=conventions, telemetry=telemetry),
        DormantWarehouseCheck(conventions=conventions, telemetry=telemetry),
        ExcessiveTimeTravelRetentionCheck(conventions=conventions, telemetry=telemetry),
    ]


def _load_plugins(telemetry: TelemetryPort | None = None) -> list[Rule]:
    """Load external rules from entry points."""
    plugin_rules = []
    try:
        # Load plugins registered under 'snowarch.audit.rules'
        all_entry_points = entry_points(group="snowarch.audit.rules")
        for entry_point in all_entry_points:
            try:
                # Expecting the entry point to point to a Rule class or list of Rule classes
                loaded_obj = entry_point.load()

                # If it's a class, instantiate it
                if isinstance(loaded_obj, type):
                    plugin_rules.append(loaded_obj())
                # If it's a function, call it
                elif callable(loaded_obj):
                    result = loaded_obj()
                    if isinstance(result, list):
                        plugin_rules.extend(result)
                    else:
                        plugin_rules.append(result)
                # If it's a list, extend
                elif isinstance(loaded_obj, list):
                    plugin_rules.extend(loaded_obj)

            except (ImportError, AttributeError, TypeError, RuntimeError) as e:
                if telemetry:
                    telemetry.error(f"Failed to load plugin {entry_point.name}: {e}")

    except (ImportError, AttributeError, RuntimeError) as e:
        if telemetry:
            telemetry.warning(f"Plugin loading warning: {e}")

    return plugin_rules


def discover_custom_rules(folder_path: str, telemetry: TelemetryPort | None = None) -> list[Rule]:
    """Dynamically discover rules in a local folder."""
    rules = []
    folder = Path(folder_path)

    if not folder.exists():
        return []

    # Add folder to path so imports work if they are relative
    sys.path.append(str(folder.resolve()))

    for py_file in folder.glob("*.py"):
        filename: str = py_file.name
        if filename.startswith("__"):
            continue

        rules.extend(_load_and_inspect_module(py_file, telemetry))

    # Clean up sys.path
    with contextlib.suppress(ValueError):
        sys.path.remove(str(folder.resolve()))

    return rules


def _load_and_inspect_module(py_file: Path, telemetry: TelemetryPort | None) -> list[Rule]:
    """Helper to load a module and inspect for rules."""
    module_name = py_file.stem
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if not spec or not spec.loader:
        return []

    module = importlib.util.module_from_spec(spec)
    try:
        loader = spec.loader
        loader.exec_module(module)
    except Exception as e:
        msg = f"Failed to load custom rule file {py_file}: {e}"
        if telemetry:
            telemetry.error(msg)
        raise RuntimeError(msg) from e

    return _extract_rules_from_module(module, py_file, telemetry)


def _extract_rules_from_module(module, py_file: Path, telemetry: TelemetryPort | None) -> list[Rule]:
    """Helper to extract rules from a loaded module."""
    rules = []
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and issubclass(obj, Rule) and obj is not Rule:
            try:
                # Heuristic: try instantiating with no args
                rule_instance = obj()  # type: ignore[call-arg]
                rules.append(rule_instance)
                if telemetry:
                    telemetry.step(f"Loaded custom rule: {rule_instance.id} from {py_file.name}")
            except Exception as e:
                msg = (
                    f"Could not instantiate {name} from {py_file.name}. "
                    f"Custom rules must have a no-arg constructor or handle their own DI."
                )
                if telemetry:
                    telemetry.error(f"{msg} Error: {e}")
                raise RuntimeError(msg) from e
    return rules


def get_rules(
    evaluator: FinancialEvaluator,
    telemetry: TelemetryPort | None = None,
    custom_rules_dir: str | None = None,
    project_root: Path | None = None,
    permifrost_spec_path: str | None = None,
) -> list[Rule]:
    """Combines builtin rules with loaded plugins and custom folder rules."""
    builtin = get_all_rules(evaluator, telemetry, project_root, permifrost_spec_path=permifrost_spec_path)
    plugins = _load_plugins(telemetry)
    custom = discover_custom_rules(custom_rules_dir, telemetry) if custom_rules_dir else []
    return builtin + plugins + custom
