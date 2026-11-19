from __future__ import annotations

import sqlite3
import tempfile
import uuid
from contextlib import closing
from pathlib import Path

from ..errors import Conflict, MemoryPAError, UncertainWrite
from ..files import private_path, read_tree, write_tree
from . import Revision


class LocalStorage:
    def __init__(self, root: Path):
        self.root = private_path(root)
        self.database = self.root / "head.sqlite3"
        self.revisions = self.root / "revisions"

    def read(self) -> Revision:
        self._check_layout()
        if not self.database.exists():
            return Revision(None, {})
        try:
            with closing(
                sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
            ) as connection:
                row = connection.execute("SELECT token FROM head WHERE id = 1").fetchone()
        except sqlite3.OperationalError as exc:
            # A first writer can have opened the database before creating its head.
            if str(exc) == "no such table: head":
                return Revision(None, {})
            raise MemoryPAError("Could not read the local memory head.") from exc
        except sqlite3.Error as exc:
            raise MemoryPAError("Could not read the local memory head.") from exc
        if not row:
            return Revision(None, {})
        token = row[0]
        if (
            not isinstance(token, str)
            or len(token) != 32
            or any(character not in "0123456789abcdef" for character in token)
        ):
            raise MemoryPAError("Invalid local revision token.")
        return Revision(token, read_tree(self.revisions / token))

    def publish(self, expected, files) -> str:
        self._check_layout()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.revisions.mkdir(exist_ok=True, mode=0o700)
        token = uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=self.root, prefix=".stage-") as temporary:
            stage = Path(temporary, "tree")
            stage.mkdir(mode=0o700)
            write_tree(stage, files)
            try:
                with closing(sqlite3.connect(self.database, timeout=30)) as connection, connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS head (id INTEGER PRIMARY KEY, token TEXT NOT NULL)"
                    )
                    row = connection.execute("SELECT token FROM head WHERE id = 1").fetchone()
                    if (row[0] if row else None) != expected:
                        raise Conflict("The local workspace changed. Preview the note again.")
                    stage.rename(self.revisions / token)
                    connection.execute("INSERT OR REPLACE INTO head VALUES (1, ?)", (token,))
            except sqlite3.Error as exc:
                try:
                    if self.read().token == token:
                        return token
                except (OSError, MemoryPAError):
                    pass
                raise UncertainWrite(
                    "Could not confirm the local write. Preview again to check for an existing note."
                ) from exc
        return token

    def _check_layout(self) -> None:
        if (
            self.root.is_dir()
            and not self.database.exists()
            and any(
                not entry.name.startswith(".stage-")
                for entry in self.root.iterdir()
                if entry != self.revisions
            )
        ):
            raise MemoryPAError("Choose a new directory or an existing memory-pa workspace.")
        if self.database.is_symlink() or self.revisions.is_symlink():
            raise MemoryPAError(
                "The local head and revisions directory must be inside the workspace."
            )
