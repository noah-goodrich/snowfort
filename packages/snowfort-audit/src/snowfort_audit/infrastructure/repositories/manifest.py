import logging
from typing import Any

import yaml

from snowfort_audit.domain.protocols import FileSystemProtocol, ManifestRepositoryProtocol

logger = logging.getLogger(__name__)


class YamlManifestRepository(ManifestRepositoryProtocol):
    """Repository for loading manifest definitions from YAML."""

    def __init__(self, fs: FileSystemProtocol):
        self.fs = fs

    def load_definitions(self, path: str) -> dict[str, Any]:
        """Load definitions from manifest.yml at path."""
        manifest_path = self.fs.join_path(path, "manifest.yml")

        if not self.fs.exists(manifest_path):
            return {}

        try:
            content = self.fs.read_text(manifest_path)
            data: dict[str, Any] = yaml.safe_load(content) or {}
            return data.get("definitions", {})
        except yaml.YAMLError as e:
            logger.error("Failed to parse manifest.yml at %s: %s", manifest_path, e)
            return {}
