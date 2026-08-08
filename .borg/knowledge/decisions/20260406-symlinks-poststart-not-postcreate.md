---
id: 20260406-symlinks-poststart-not-postcreate
date: '2026-06-11'
project: snowfort
domain: infrastructure
tags:
- devcontainer
- zsh
- dotfiles
- docker
- symlinks
alternatives: []
applies_to: []
confidence: 0.9
status: active
superseded_by: null
cost_to_produce: null
source_tool: null
source_model: null
source_session: null
created_at: '2026-06-11 20:31:24.650364+00:00'
updated_at: '2026-06-11 20:31:24.650367+00:00'
---

# 20260406-symlinks-poststart-not-postcreate

## decision

Move dotfile symlink creation (ln -sf for .zshrc, .p10k.zsh) from postCreateCommand to postStartCommand in devcontainer.json

## context

zsh was not setting up correctly in the snowfort devcontainer. Symlinks existed in a working reference container (wallpaper-kit) but were missing in snowfort after a rebuild or interrupted create.

## reasoning

postCreateCommand runs only once on container creation. If the container is rebuilt or the create command is interrupted, the symlinks are never re-created even though the source volume mounts are intact. postStartCommand runs on every container start, making symlink creation idempotent and resilient to rebuilds.
