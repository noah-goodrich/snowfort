---
id: obs-20260617-cairn-first-boot-model-download-wedge
session_date: '2026-06-18'
project: snowfort
tool: claude-code
tags:
- cairn
- bge-small
- embedding-model
- docker
- first-boot
category: tool_behavior
files_involved: []
confidence: 0.9
source_model: null
source_session: 20260618-0254-snowfort
superseded_by: null
created_at: '2026-06-18 02:54:48.272194+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260617-cairn-first-boot-model-download-wedge

## content

On first boot, the local cairn server wedged silently while downloading the bge-small embedding model. The container appeared to be running but the HTTP API was unresponsive with no clear error surfaced to the caller.

## resolution

Wait for the model download to complete before issuing API requests. Check container logs explicitly on first boot (bin/cairn-up logs or docker logs) to confirm the embedding model is loaded before proceeding.
