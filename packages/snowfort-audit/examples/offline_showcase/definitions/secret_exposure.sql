-- STAT_003: Potential hardcoded secret (example only - do not use real secrets)
-- Intended to trigger: "Potential hardcoded secret detected"
CREATE USER svc_loader
  PASSWORD = 'ChangeMeInProd!'
  DEFAULT_ROLE = LOADER_ROLE;
