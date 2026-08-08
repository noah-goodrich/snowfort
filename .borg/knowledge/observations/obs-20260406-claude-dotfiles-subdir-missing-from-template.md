---
id: obs-20260406-claude-dotfiles-subdir-missing-from-template
session_date: '2026-06-11'
project: snowfort
tool: cursor
tags:
- devcontainer
- docker-compose
- dotfiles
- claude
- template
- volume-mount
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 20:31:24.653650+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260406-claude-dotfiles-subdir-missing-from-template

## content

The canonical STANDARD DOTFILES BLOCK in docker-compose.yml (and docker-compose.base.yml) only mounted ~/.config/dotfiles/zsh. The ~/.config/dotfiles/claude subdirectory — which contains Claude Code plugins (dev-tools, noah-strategy, etc.) — was never included. Every project spun up from the base template silently lacked these plugins with no error at container start. The gap was systemic across at least snowfort and wallpaper-kit.

## resolution

Add '~/.config/dotfiles/claude:/home/dev/.config/dotfiles/claude:cached' to the STANDARD DOTFILES BLOCK in docker-compose.base.yml and backfill all existing projects. A rebuild is required for the mount to take effect — the config change alone is insufficient.
