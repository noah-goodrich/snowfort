"""Local filesystem gateway (vendored)."""

import os
from collections.abc import Generator
from pathlib import Path


class LocalFileSystemGateway:
    """Implementation of FileSystemProtocol using pathlib."""

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        Path(path).write_text(content, encoding=encoding)

    def join_path(self, *paths: str) -> str:
        return str(Path(*paths))

    def walk(self, top: str) -> Generator[tuple[str, list[str], list[str]], None, None]:
        yield from os.walk(top)

    def make_dirs(self, path: str, exist_ok: bool = True) -> None:
        Path(path).mkdir(parents=True, exist_ok=exist_ok)

    def get_cwd(self) -> str:
        return str(Path.cwd())

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def get_parent(self, path: str) -> str:
        return str(Path(path).parent)
