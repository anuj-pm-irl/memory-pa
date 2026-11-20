"""Remember the selected store outside the portable workspace."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .errors import MemoryPAError
from .files import json_bytes, parse_json, private_path
from .storage import default_local_path

MAX_SETTINGS_BYTES = 16 * 1024


@dataclass(frozen=True)
class StoreSelection:
    store: str | None
    git_branch: str
    aws_profile: str | None
    source: str

    def describe(self) -> dict:
        target = self.store
        if not target or "://" not in target:
            target = str(Path(target).expanduser().resolve() if target else default_local_path())
        elif _has_url_credentials_or_options(target):
            target = "<store address hidden>"
        return {
            "store": target,
            "git_branch": self.git_branch,
            "aws_profile": self.aws_profile,
            "source": self.source,
        }


def _has_url_credentials_or_options(target: str) -> bool:
    url = urlsplit(target)
    return bool(
        url.query
        or url.fragment
        or url.password is not None
        or (url.username is not None and url.scheme != "git+ssh")
    )


def _settings_path() -> Path:
    override = os.environ.get("MEMORY_PA_CONFIG")
    path = Path(override).expanduser() if override else Path.home() / ".memory-pa" / "config.json"
    if path.is_symlink():
        raise MemoryPAError("Choose a regular file for memory-pa settings.")
    return private_path(path)


def _load() -> dict:
    path = _settings_path()
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_SETTINGS_BYTES + 1)
    except FileNotFoundError:
        return {}
    try:
        if len(data) > MAX_SETTINGS_BYTES:
            raise MemoryPAError("Settings file is too large.")
        value = parse_json(data, "memory-pa settings")
        if (
            not isinstance(value, dict)
            or set(value) != {"store", "git_branch", "aws_profile"}
            or not all(
                isinstance(value[name], str) and value[name] for name in ("store", "git_branch")
            )
            or (value["aws_profile"] is not None and not isinstance(value["aws_profile"], str))
        ):
            raise MemoryPAError("Invalid saved settings.")
    except MemoryPAError as exc:
        raise MemoryPAError(
            "Could not read saved settings. Use --store with init --remember to set the default again."
        ) from exc
    return value


def select_store(store, git_branch, aws_profile) -> StoreSelection:
    saved = {}
    if store:
        source = "flag"
    elif environment := os.environ.get("MEMORY_PA_STORE"):
        store, source = environment, "environment"
    else:
        saved = _load()
        store = saved.get("store")
        source = "saved" if store else "default"
    branch = git_branch or os.environ.get("MEMORY_PA_GIT_BRANCH") or saved.get("git_branch", "main")
    return StoreSelection(store, branch, aws_profile or saved.get("aws_profile"), source)


def settings_data(store: str, git_branch: str, aws_profile: str | None) -> bytes:
    if "://" in store and _has_url_credentials_or_options(store):
        raise MemoryPAError(
            "Use a store address without credentials, query parameters, or fragments."
        )
    data = json_bytes({"store": store, "git_branch": git_branch, "aws_profile": aws_profile})
    if len(data) > MAX_SETTINGS_BYTES:
        raise MemoryPAError("The store settings are too large to remember.")
    return data


def remember(data: bytes) -> None:
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent, prefix=".settings-") as directory:
            stage = Path(directory, "config.json")
            with os.fdopen(
                os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
            ) as stream:
                stream.write(data)
            stage.replace(path)
    except (OSError, MemoryPAError) as exc:
        raise MemoryPAError(
            "Your workspace is ready, but the default could not be saved. Check your settings file."
        ) from exc
