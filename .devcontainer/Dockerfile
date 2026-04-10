# Extends the shared base devcontainer image.
# Base provides: zsh, neovim, tmux, git, ssh, node.js, claude-code CLI.
#
# To rebuild the base locally:
#   docker build -f ~/.config/dotfiles/devcontainer/Dockerfile.base -t devcontainer-base:local .
FROM devcontainer-base:local

# Project-specific: keyring backend for Snowfort auth (mfa/pat) in headless container
RUN pip install --no-cache-dir keyrings.alt
