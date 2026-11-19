import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_memory import example


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store = self.tmp / "private-workspace"

    def call(self, *args, body=None, status=0):
        result = subprocess.run(
            [sys.executable, "-m", "memory_pa", "--store", str(self.store), *args],
            capture_output=True,
            input=body,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout

    def preview(self, proposal):
        return json.loads(self.call("add", "--proposal", "-", "--json", body=json.dumps(proposal)))

    def apply(self, proposal, preview, status=0):
        return json.loads(
            self.call(
                "add",
                "--proposal",
                "-",
                "--json",
                "--apply",
                preview["apply_token"],
                body=json.dumps(proposal),
                status=status,
            )
        )

    def test_demo_uses_fictional_workspace(self):
        output = self.call("demo")
        self.assertIn("Rainy Robot Club", output)
        self.assertIn("Decision", output)
        self.assertIn("Open action", output)
        self.assertIn("#source-text", output)
        self.assertFalse(self.store.exists())

    def test_different_processes_can_capture_and_recall(self):
        self.call("init")
        first = self.preview(example())
        modified = {**example(), "summary": "A different proposal."}
        self.assertEqual(self.apply(modified, first, status=3)["status"], "conflict")
        self.assertEqual(self.apply(example(), first)["status"], "saved")
        self.assertEqual(self.apply(example(), first)["status"], "duplicate")
        search = json.loads(self.call("search", "blue lantern", "--json"))
        self.assertTrue(all(item["note"] == first["note"] for item in search))
        self.assertEqual(
            self.call("show", first["note"], "--section", "source-text"), example()["text"]
        )
        self.assertEqual(json.loads(self.call("validate", "--json"))["notes"], 1)

    def test_file_input_and_export_import(self):
        self.call("init")
        source = self.tmp / "selected.txt"
        source.write_text("A cedar bench for the smallest robot.", encoding="utf-8")
        arguments = (
            "add",
            "--file",
            str(source),
            "--title",
            "Bench",
            "--topic",
            "robots",
            "--json",
        )
        preview = json.loads(self.call(*arguments))
        self.call(*arguments, "--apply", preview["apply_token"])
        exported = self.tmp / "export"
        self.call("export", str(exported))
        self.store = self.tmp / "fresh-workspace"
        self.call("init", "--from", str(exported))
        self.assertIn("cedar bench", self.call("show", preview["note"], "--section", "source-text"))
