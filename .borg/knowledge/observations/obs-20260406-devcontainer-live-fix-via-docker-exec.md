---
id: obs-20260406-devcontainer-live-fix-via-docker-exec
session_date: '2026-06-11'
project: snowfort
tool: cursor
tags:
- devcontainer
- docker
- docker-exec
- hotfix
- symlinks
category: pattern_discovered
files_involved: []
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 20:31:24.654047+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260406-devcontainer-live-fix-via-docker-exec

## content

For fixes that don't require new volume mounts (e.g., creating missing symlinks), docker exec can apply the fix to a live container immediately without a rebuild. This is useful when a rebuild would be disruptive or slow. Fixes that DO require new mounts (e.g., adding a volume in docker-compose.yml) cannot be applied this way and require a full rebuild to take effect.

## resolution

Use docker exec for idempotent in-container fixes (symlinks, file writes to already-mounted paths). Schedule rebuilds only when mount changes are needed. Document which category a fix falls into before deciding on the repair approach.
