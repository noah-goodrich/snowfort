---
id: obs-20260406-postcreate-symlinks-silently-lost-on-rebuild
session_date: '2026-06-11'
project: snowfort
tool: cursor
tags:
- devcontainer
- docker
- symlinks
- dotfiles
- zsh
- postCreateCommand
category: gotcha
files_involved: []
confidence: 0.9
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 20:31:24.653118+00:00'
updated_at: '2026-07-24 03:52:21.933874+00:00'
---

# obs-20260406-postcreate-symlinks-silently-lost-on-rebuild

## content

Dotfile symlinks placed by postCreateCommand are silently lost on container rebuild. The volume mounts remain intact and ls of the mount point shows the source files correctly, so nothing appears broken — but the symlinks in $HOME are gone. zsh then fails to load its config without a clear error pointing to the missing symlinks. This is a silent failure that looks like a shell misconfiguration rather than a lifecycle hook issue.

## resolution

Move all idempotent setup commands (ln -sf, etc.) from postCreateCommand to postStartCommand so they are re-applied on every container start, surviving rebuilds automatically.
