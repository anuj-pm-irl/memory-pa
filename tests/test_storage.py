import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from test_memory import example

from memory_pa.errors import Conflict, MemoryPAError, UncertainWrite
from memory_pa.files import export_tree, read_tree
from memory_pa.memory import Workspace, empty_workspace
from memory_pa.storage.git import GitStorage
from memory_pa.storage.local import LocalStorage
from memory_pa.storage.s3 import S3Storage

try:
    import boto3
    from moto import mock_aws
except ImportError:
    mock_aws = None


class StorageContract:
    def test_workspace_and_export_round_trip(self):
        self.assertIsNone(self.store.read().token)
        first = self.store.publish(None, empty_workspace())
        capture = Workspace(self.store.read().files).prepare(example())
        second = self.store.publish(first, capture.files)
        self.assertNotEqual(first, second)
        read = self.store.read()
        self.assertEqual(second, read.token)
        self.assertEqual(capture.files, read.files)
        with tempfile.TemporaryDirectory() as directory:
            exported = Path(directory, "copy")
            export_tree(exported, read.files)
            self.assertEqual(read_tree(exported), capture.files)
            imported = LocalStorage(Path(directory, "imported"))
            imported.publish(None, read_tree(exported))
            self.assertEqual(imported.read().files, capture.files)
        with self.assertRaises(Conflict):
            self.store.publish(first, empty_workspace())
        self.assertEqual(self.store.read().token, second)

    def test_create_only_on_empty_revision(self):
        first = self.store.publish(None, empty_workspace())
        with self.assertRaises(Conflict):
            self.store.publish(None, empty_workspace())
        self.assertEqual(self.store.read().token, first)

    def test_invalid_paths_leave_head_intact(self):
        good = empty_workspace()
        base = self.store.publish(None, good)
        with self.assertRaises(MemoryPAError):
            self.store.publish(base, {**good, "../outside.md": b"wrong"})
        self.assertEqual(self.store.read().files, good)

    def concurrent_writers(self):
        start = self.store.publish(None, empty_workspace())
        workspace = Workspace(self.store.read().files)
        a = workspace.prepare(example()).files
        b = workspace.prepare(
            {**example(), "title": "Another event", "text": "A different blue lantern meeting."}
        ).files

        def publish(files):
            try:
                return self.store.publish(start, files)
            except Conflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(publish, (a, b)))
        self.assertEqual(results.count("conflict"), 1)
        self.assertIn(self.store.read().files, [a, b])


class LocalTests(StorageContract, unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = LocalStorage(Path(directory, "workspace"))

    def test_concurrent_writers(self):
        self.concurrent_writers()

    def test_interrupted_staging_does_not_move_head(self):
        revision = self.store.publish(None, empty_workspace())
        with (
            patch("memory_pa.storage.local.write_tree", side_effect=OSError("interrupted")),
            self.assertRaises(OSError),
        ):
            self.store.publish(revision, empty_workspace())
        self.assertEqual(self.store.read().token, revision)

    def test_public_source_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "memory-pa"\n', encoding="utf-8"
            )
            with self.assertRaises(MemoryPAError):
                LocalStorage(root / "workspace")


@unittest.skipUnless(shutil.which("git"), "Git is required")
class GitTests(StorageContract, unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()), "private.git")
        subprocess.run(
            ["git", "init", "--bare", "--quiet", str(directory)], check=True, capture_output=True
        )
        self.store = GitStorage(directory.as_uri(), "memory")

    def test_concurrent_writers(self):
        self.concurrent_writers()

    def test_public_git_target_is_rejected(self):
        for url in (
            "https://github.com/anuj-pm-irl/memory-pa.git",
            "ssh://git@ssh.github.com:443/ANUJ-PM-IRL/MEMORY-PA/",
        ):
            with self.subTest(url=url), self.assertRaises(MemoryPAError):
                GitStorage(url)


@unittest.skipUnless(mock_aws, "Install the test extra for S3 conformance")
class S3Tests(StorageContract, unittest.TestCase):
    def setUp(self):
        self.enterContext(mock_aws())
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="fictional-memory-tests")
        self.store = S3Storage("s3://fictional-memory-tests/conformance", client=client)

    def test_head_update_receipt_recovers_when_response_is_lost(self):
        original = self.store.client.put_object

        def lost_response(**kwargs):
            result = original(**kwargs)
            if kwargs["Key"].endswith("/HEAD.json"):
                raise OSError("test lost response")
            return result

        files = empty_workspace()
        with patch.object(self.store.client, "put_object", side_effect=lost_response):
            revision = self.store.publish(None, files)
        self.assertEqual(self.store.read().token, revision)
        self.assertEqual(self.store.read().files, files)

    def test_staged_archive_is_invisible_if_head_write_fails(self):
        original = self.store.client.put_object

        def fail_head(**kwargs):
            if kwargs["Key"].endswith("/HEAD.json"):
                raise OSError("test head write failure")
            return original(**kwargs)

        files = empty_workspace()
        base = self.store.publish(None, files)
        with (
            patch.object(self.store.client, "put_object", side_effect=fail_head),
            self.assertRaises(UncertainWrite),
        ):
            self.store.publish(base, empty_workspace())
        self.assertEqual(self.store.read().files, files)


@unittest.skipUnless(
    os.getenv("MEMORY_PA_TEST_S3"), "Set a private S3 test prefix to test against AWS"
)
class LiveS3Tests(StorageContract, unittest.TestCase):
    def setUp(self):
        address = os.environ["MEMORY_PA_TEST_S3"].rstrip("/")
        self.store = S3Storage(f"{address}/test-{uuid.uuid4().hex}")
