"""Storage interface shared by the CLI and external adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol

from ..errors import MemoryPAError


@dataclass(frozen=True)
class Revision:
    token: str | None
    files: Mapping[str, bytes]


class Storage(Protocol):
    def read(self) -> Revision:
        """Return the current snapshot, or Revision(None, {}) for an empty destination."""

    def publish(self, expected: str | None, files: Mapping[str, bytes]) -> str:
        """Store a complete snapshot only if expected is still current. Return its new token."""


def open_storage(target: str | None, branch: str = "main") -> Storage:
    if not target or "://" not in target:
        from .local import LocalStorage

        path = Path(target) if target else Path.home() / ".memory-pa" / "workspaces" / "default"
        return LocalStorage(path)

    scheme = target.split("://", 1)[0]
    if scheme in {"git+https", "git+ssh", "git+file"}:
        from .git import GitStorage

        return GitStorage(target.removeprefix("git+"), branch)

    if scheme == "s3":
        from .s3 import S3Storage

        return S3Storage(target)

    adapters = list(entry_points(group="memory_pa.storage", name=scheme))
    if len(adapters) != 1:
        raise MemoryPAError(
            "Choose a local path, git+https, git+ssh, git+file, s3, or an installed storage adapter."
        )
    return adapters[0].load()(target)
