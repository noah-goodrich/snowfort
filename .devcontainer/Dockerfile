# Extends the shared base devcontainer image.
# Base provides: zsh, neovim, tmux, git, ssh, node.js, claude-code CLI.
#
# To rebuild the base locally:
#   docker build -f ~/.config/dotfiles/devcontainer/Dockerfile.base -t devcontainer-base:local .
FROM devcontainer-base:local

# GitHub CLI for releases and PR management
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update -qq && apt-get install -y -qq gh && rm -rf /var/lib/apt/lists/*

# Project-specific: keyring backend for Snowfort auth (mfa/pat) in headless container
RUN pip install --no-cache-dir keyrings.alt
