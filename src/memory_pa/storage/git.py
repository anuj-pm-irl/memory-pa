from __future__ import annotations

import io
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from ..errors import Conflict, MemoryPAError, UncertainWrite
from ..files import check_limits, check_path, check_tree, is_public_repo, private_path
from . import Revision


class GitStorage:
    def __init__(self, remote: str, branch: str = "main"):
        self._check_remote(remote)
        self.remote = remote
        self.ref = f"refs/heads/{branch}"

    @staticmethod
    def _check_remote(remote: str) -> None:
        if is_public_repo(remote):
            raise MemoryPAError("Choose a private Git repository for your memory workspace.")
        parsed = urlsplit(remote)
        if (
            parsed.scheme == "file"
            and parsed.netloc in {"", "localhost"}
            and parsed.path.startswith("/")
        ):
            private_path(Path(url2pathname(parsed.path)))
            return
        if (
            parsed.scheme not in {"https", "ssh"}
            or not parsed.hostname
            or not parsed.path.strip("/")
            or parsed.query
            or parsed.fragment
            or parsed.password
            or (parsed.scheme == "https" and parsed.username)
        ):
            raise MemoryPAError(
                "Use a Git HTTPS or SSH URL without credentials, or a local file URL."
            )

    @contextmanager
    def _repo(self):
        with tempfile.TemporaryDirectory(prefix="memory-pa-git-") as temporary:
            env = {
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "GIT_DIR",
                    "GIT_WORK_TREE",
                    "GIT_COMMON_DIR",
                    "GIT_INDEX_FILE",
                    "GIT_OBJECT_DIRECTORY",
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                    "GIT_NAMESPACE",
                    "GIT_CONFIG",
                    "GIT_QUARANTINE_PATH",
                }
            }
            env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "https:ssh:file"})

            def run(*args, data=None, allowed=(0,)):
                try:
                    result = subprocess.run(
                        [
                            "git",
                            "-c",
                            "http.followRedirects=false",
                            "-c",
                            f"core.hooksPath={temporary}/no-hooks",
                            *args,
                        ],
                        cwd=temporary,
                        env=env,
                        input=data,
                        capture_output=True,
                        timeout=120,
                        check=False,
                    )
                except FileNotFoundError as exc:
                    raise MemoryPAError("Install Git to use a Git workspace.") from exc
                if result.returncode not in allowed:
                    raise subprocess.CalledProcessError(
                        result.returncode, result.args, result.stdout, result.stderr
                    )
                return result

            try:
                run("init", "--bare", "--quiet", "--object-format=sha1")
                run("check-ref-format", self.ref)
                run("remote", "add", "origin", self.remote)
                for options in (("--all",), ("--push", "--all")):
                    for url in (
                        run("remote", "get-url", *options, "origin").stdout.decode().splitlines()
                    ):
                        self._check_remote(url)
                yield run
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise MemoryPAError(
                    "Git operation failed. Check the branch, repository access, and Git credentials."
                ) from exc

    def _remote_tip(self, run) -> str | None:
        result = run("ls-remote", "--refs", "--exit-code", "origin", self.ref, allowed=(0, 2))
        if result.returncode == 2:
            return None
        raw = result.stdout.decode("ascii").strip().split("\t")
        if len(raw) != 2 or raw[1] != self.ref or not re.fullmatch(r"[a-f0-9]{40}", raw[0]):
            raise MemoryPAError("Expected a single Git branch with SHA-1 object IDs.")
        return raw[0]

    def read(self) -> Revision:
        with self._repo() as run:
            if not self._remote_tip(run):
                return Revision(None, {})
            run("fetch", "--quiet", "--no-tags", "--depth=1", "origin", self.ref)
            head = run("rev-parse", "FETCH_HEAD").stdout.decode("ascii").strip()
            entries = run("ls-tree", "-r", "-l", "-z", head).stdout.split(b"\0")[:-1]
            blobs = []
            total = 0
            for entry in entries:
                attributes, name = entry.split(b"\t", 1)
                mode, kind, oid, size = attributes.split()
                if mode != b"100644" or kind != b"blob":
                    raise MemoryPAError("The Git branch must contain regular memory-pa files.")
                path = name.decode("utf-8")
                check_path(path)
                count = int(size)
                total += count
                check_limits(len(entries), count, total)
                blobs.append((path, oid, count))
            response = run("cat-file", "--batch", data=b"".join(oid + b"\n" for _, oid, _ in blobs))
            stream = io.BytesIO(response.stdout)
            files = {}
            for path, oid, size in blobs:
                if stream.readline().split() != [oid, b"blob", str(size).encode("ascii")]:
                    raise MemoryPAError("Invalid blob response from Git.")
                files[path] = stream.read(size)
                if stream.read(1) != b"\n":
                    raise MemoryPAError("Incomplete blob response from Git.")
            return Revision(head, files)

    def publish(self, expected, files) -> str:
        check_tree(files)
        with self._repo() as run:
            if self._remote_tip(run) != expected:
                raise Conflict("The Git branch changed. Preview the note again.")
            parents = []
            if expected:
                run("fetch", "--quiet", "--no-tags", "--depth=1", "origin", self.ref)
                fetched = run("rev-parse", "FETCH_HEAD").stdout.decode("ascii").strip()
                if fetched != expected:
                    raise Conflict("The Git branch changed. Preview the note again.")
                parents = ["-p", expected]
            index_entries = []
            for path, body in sorted(files.items()):
                oid = run("hash-object", "-w", "--stdin", data=body).stdout.strip()
                index_entries.append(b"100644 " + oid + b"\t" + path.encode("ascii") + b"\0")
            run("update-index", "-z", "--index-info", data=b"".join(index_entries))
            tree = run("write-tree").stdout.decode("ascii").strip()
            commit = (
                run(
                    "-c",
                    "user.name=memory-pa",
                    "-c",
                    "user.email=memory-pa@memory-pa.invalid",
                    "-c",
                    "commit.gpgSign=false",
                    "commit-tree",
                    tree,
                    *parents,
                    "-m",
                    "Update memory workspace",
                )
                .stdout.decode("ascii")
                .strip()
            )
            try:
                run(
                    "push",
                    "--porcelain",
                    f"--force-with-lease={self.ref}:{expected or ''}",
                    "origin",
                    f"{commit}:{self.ref}",
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                try:
                    current = self._remote_tip(run)
                    if current == commit:
                        return commit
                    if current != expected:
                        raise Conflict("The Git branch changed. Preview the note again.") from exc
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
                raise UncertainWrite(
                    "Could not confirm the Git write. Preview again to check for an existing note."
                ) from exc
            return commit
