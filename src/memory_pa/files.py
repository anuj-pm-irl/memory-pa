"""Read, validate, and move a portable tree without following links."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .errors import MemoryPAError

MAX_FILES = 10_000
MAX_TREE_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
PUBLIC_REPO = "anuj-pm-irl/memory-pa"
PUBLIC_REPO_URL = f"https://github.com/{PUBLIC_REPO}"
SEGMENT = re.compile(r"[a-z0-9_][a-z0-9._-]{0,99}\Z")
DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value) -> bytes:
    try:
        return (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (ValueError, OverflowError, RecursionError) as exc:
        raise MemoryPAError("Expected finite JSON values and valid UTF-8 text.") from exc


def parse_json(raw: bytes, label: str):
    def unique_object(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate field")
        return result

    def invalid_constant(_):
        raise ValueError("non-finite number")

    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
    except (ValueError, RecursionError) as exc:
        raise MemoryPAError(f"Invalid UTF-8 JSON in {label}.") from exc


def check_path(name: str) -> None:
    if not isinstance(name, str):
        raise MemoryPAError("Snapshot paths must be strings.")
    parts = name.split("/")
    if len(name) > 200 or any(
        not SEGMENT.fullmatch(part) or part.endswith(".") or DEVICE.fullmatch(part)
        for part in parts
    ):
        raise MemoryPAError("The snapshot contains an unsafe or non-portable file path.")


def check_limits(count: int, size: int, total: int) -> None:
    if count > MAX_FILES or size > MAX_FILE_BYTES or total > MAX_TREE_BYTES:
        raise MemoryPAError("Snapshot exceeds the v1 size limit.")


def check_tree(files) -> None:
    total = 0
    for name, data in files.items():
        check_path(name)
        parent = posixpath.dirname(name)
        while parent:
            if parent in files:
                raise MemoryPAError("A snapshot path cannot be both a file and a directory.")
            parent = posixpath.dirname(parent)
        if not isinstance(data, bytes):
            raise MemoryPAError("A snapshot must map paths to bytes.")
        total += len(data)
        check_limits(len(files), len(data), total)


def read_tree(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise MemoryPAError("Expected a directory containing a memory-pa snapshot.")
    files = {}
    total = 0
    for directory, folders, filenames in os.walk(root, followlinks=False):
        for name in folders:
            path = Path(directory, name)
            check_path(path.relative_to(root).as_posix())
            if path.is_symlink():
                raise MemoryPAError("Snapshot directories must be regular directories.")
        for name in filenames:
            path = Path(directory, name)
            relative = path.relative_to(root).as_posix()
            check_path(relative)
            if path.is_symlink() or not path.is_file():
                raise MemoryPAError("Snapshot entries must be regular files.")
            size = path.stat().st_size
            total += size
            check_limits(len(files) + 1, size, total)
            files[relative] = path.read_bytes()
    check_tree(files)
    return files


def write_tree(root: Path, files) -> None:
    check_tree(files)
    for name, data in sorted(files.items()):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def export_tree(destination: Path, files) -> None:
    destination = private_path(destination)
    if destination.exists():
        raise MemoryPAError("Choose a new directory for the export.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=destination.parent, prefix=".memory-pa-export-"
    ) as temporary:
        stage = Path(temporary, "tree")
        stage.mkdir(mode=0o700)
        write_tree(stage, files)
        stage.rename(destination)


def is_public_repo(url: str) -> bool:
    parsed = urlsplit(url)
    host = parsed.hostname
    path = parsed.path
    if not host:
        scp = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):/*(.+)", url)
        if not scp:
            return False
        host, path = scp.groups()
    repo = (
        posixpath.normpath("/" + unquote(path).lower().lstrip("/")).strip("/").removesuffix(".git")
    )
    return (
        host.lower().rstrip(".") in {"github.com", "www.github.com", "ssh.github.com"}
        and repo == PUBLIC_REPO
    )


def private_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    for parent in (path, *path.parents):
        project = parent / "pyproject.toml"
        if project.is_file():
            try:
                with project.open("rb") as metadata:
                    name = tomllib.load(metadata).get("project", {}).get("name")
            except (OSError, ValueError):
                name = None
            if name == "memory-pa":
                raise MemoryPAError("Choose a memory location outside the memory-pa code checkout.")
        git_marker = parent / ".git"
        if git_marker.exists():
            try:
                remotes = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(parent),
                        "config",
                        "--local",
                        "--get-regexp",
                        r"^remote\..*\.(url|pushurl)$",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                ).stdout.splitlines()
            except (OSError, subprocess.TimeoutExpired):
                remotes = ()
            if any(is_public_repo(line.partition(" ")[2]) for line in remotes):
                raise MemoryPAError(
                    "Choose a memory location outside the public memory-pa checkout."
                )
    return path
