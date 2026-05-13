-- Snowfort Audit Dashboard Schema
-- Creates the persistence layer for scan history used by the Streamlit dashboard.
-- Safe to re-run (all statements use IF NOT EXISTS).

CREATE DATABASE IF NOT EXISTS SNOWFORT;
CREATE SCHEMA IF NOT EXISTS SNOWFORT.AUDIT;

CREATE TABLE IF NOT EXISTS SNOWFORT.AUDIT.SCAN_METADATA (
    scan_id             VARCHAR(36)     NOT NULL,
    scanned_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    account_id          VARCHAR,
    compliance_score    FLOAT,
    grade               VARCHAR(1),
    total_violations    INT,
    critical_count      INT,
    high_count          INT,
    medium_count        INT,
    low_count           INT,
    pillar_scores       VARIANT,
    pillar_grades       VARIANT,
    billing_model       VARCHAR,
    reliable            BOOLEAN,
    total_rules         INT,
    errored_rules       INT,
    PRIMARY KEY (scan_id)
);

CREATE TABLE IF NOT EXISTS SNOWFORT.AUDIT.SCAN_VIOLATIONS (
    scan_id             VARCHAR(36)     NOT NULL,
    rule_id             VARCHAR         NOT NULL,
    resource_name       VARCHAR,
    message             VARCHAR,
    severity            VARCHAR,
    pillar              VARCHAR,
    category            VARCHAR,
    remediation_key     VARCHAR,
    rationale           VARCHAR,
    quick_win           BOOLEAN,
    FOREIGN KEY (scan_id) REFERENCES SNOWFORT.AUDIT.SCAN_METADATA(scan_id)
);
