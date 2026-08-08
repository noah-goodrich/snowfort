---
id: devcontainer-dotfiles-debug-with-reference
project: snowfort
domain: infrastructure
tags:
- devcontainer
- dotfiles
- debugging
- docker
- zsh
preconditions: []
steps:
- Identify a project whose devcontainer shell environment is known to work correctly
  (the reference).
- Side-by-side compare devcontainer.json and docker-compose.yml between the broken
  and reference projects, focusing on volume mounts and lifecycle hooks (postCreateCommand,
  postStartCommand, postAttachCommand).
- Verify that all expected source paths exist on the host (e.g., ~/.config/dotfiles/zsh,
  ~/.config/dotfiles/claude).
- Inside the broken container, check whether symlink targets exist (ls -la ~/) and
  whether the expected files are reachable via the mount (ls ~/.config/dotfiles/).
- Apply the minimal diff to bring the broken project in line with the reference.
- For symlink issues that don't require a rebuild, apply the fix immediately via docker
  exec rather than waiting for a full rebuild.
- For mount issues, apply the config change and schedule a rebuild; note that the
  fix won't be live until rebuild.
pitfalls:
- Volume mounts appearing correct is not proof the shell is configured — symlinks
  in the home directory may still be missing if postCreateCommand was interrupted
  or the container was rebuilt.
- The reference container may itself be missing mounts (as wallpaper-kit was missing
  the claude mount) — being 'working enough' doesn't mean it's complete.
- postCreateCommand changes take effect immediately on next create but NOT on a simple
  container restart; postStartCommand changes take effect on next start without rebuild.
cost_estimate: null
times_applied: 0
last_applied: null
confidence: 0.7
source_model: null
source_session: null
superseded_by: null
created_at: '2026-06-11 20:31:24.652451+00:00'
updated_at: '2026-06-11 20:31:24.652452+00:00'
---

# devcontainer-dotfiles-debug-with-reference

## description

Debug a broken devcontainer shell environment by diffing against a known-working reference container rather than reasoning from scratch.
