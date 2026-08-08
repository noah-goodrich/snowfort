---
id: 20260616-nosec-annotations-with-rationale
date: '2026-06-16'
project: snowfort
domain: code-quality
tags:
- bandit
- security
- static-analysis
- ci
alternatives: []
applies_to: []
confidence: 0.7
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-16 10:27:07.929419+00:00'
updated_at: '2026-06-16 10:27:07.929420+00:00'
---

# 20260616-nosec-annotations-with-rationale

## decision

Use inline `# nosec B608/B108` annotations with explicit rationale comments rather than blanket suppression or bandit config exclusions

## context

Bandit was a required CI check but flagged 8 locations across security and query-building modules for SQL injection (B608) and temp file (B108) patterns that were intentional/safe by design

## reasoning

Inline annotations keep suppression co-located with the code being suppressed, making it auditable. Blanket config exclusions would hide legitimate future violations. Requiring rationale comments means the next reviewer understands why the suppression is safe.
