import json
import os
import shutil
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
        self.settings = self.tmp / "settings" / "config.json"
        self.environment = {
            name: value
            for name, value in os.environ.items()
            if name not in {"MEMORY_PA_STORE", "MEMORY_PA_GIT_BRANCH"}
        }
        self.environment["MEMORY_PA_CONFIG"] = str(self.settings)

    def call(self, *args, body=None, status=0, use_default=False, cwd=None, environment=None):
        location = [] if use_default else ["--store", str(self.store)]
        result = subprocess.run(
            [sys.executable, "-m", "memory_pa", *location, *args],
            capture_output=True,
            input=body,
            text=True,
            encoding="utf-8",
            check=False,
            cwd=cwd,
            env={**self.environment, **(environment or {})},
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
        self.assertIn("Stark Archive", output)
        self.assertIn("Loaded 18 notes", output)
        self.assertIn("Happy Hogan", output)
        self.assertIn("Open action", output)
        self.assertIn("June 19, 2032 · Fictional replay", output)
        self.assertIn("Reminder preview from JARVIS · To Happy Hogan", output)
        self.assertIn("#source-text", output)
        demo = json.loads(self.call("demo", "--json"))
        self.assertEqual(demo["results"][0]["date"], "2032-06-07")
        preview = demo["reminder_preview"]
        self.assertEqual(preview["recipient"], "Happy Hogan")
        self.assertEqual(
            preview["message"],
            "Happy, please bring the sample menu cards to the June 20 handoff dry run.",
        )
        self.assertFalse(self.store.exists())
        self.assertFalse(self.settings.exists())

    def test_remember_a_relative_folder_for_future_commands(self):
        folder = self.tmp / "My memory folder"
        result = json.loads(
            self.call(
                "--store",
                folder.name,
                "init",
                "--remember",
                "--json",
                use_default=True,
                cwd=self.tmp,
            )
        )
        self.assertTrue(result["default_saved"])
        self.assertTrue(folder.is_dir())
        config = json.loads(self.call("config", "--json", use_default=True))
        self.assertEqual(config["store"], str(folder.resolve()))
        self.assertEqual(config["source"], "saved")
        state = json.loads(self.call("validate", "--json", use_default=True))
        self.assertEqual(state["workspace_id"], result["workspace_id"])
        draft = json.dumps(example())
        ready = json.loads(
            self.call("add", "--proposal", "-", "--json", body=draft, use_default=True)
        )
        self.call(
            "add", "--proposal", "-", "--apply", ready["apply_token"], body=draft, use_default=True
        )
        hits = json.loads(self.call("search", "blue lantern", "--json", use_default=True))
        self.assertTrue(any(hit["note"] == ready["note"] for hit in hits))

    def test_flags_and_environment_take_precedence_over_the_saved_store(self):
        self.call("init", "--remember")
        override = self.tmp / "a different folder"
        environment = {"MEMORY_PA_STORE": str(override)}
        active = json.loads(
            self.call("config", "--json", use_default=True, environment=environment)
        )
        self.assertEqual(active["store"], str(override.resolve()))
        self.assertEqual(active["source"], "environment")
        using_flag = json.loads(self.call("config", "--json", environment=environment))
        self.assertEqual(using_flag["store"], str(self.store.resolve()))
        self.assertEqual(using_flag["source"], "flag")
        self.assertFalse(override.exists())

    def test_unsuccessful_setup_keeps_the_previous_default(self):
        self.call("init", "--remember")
        before = self.settings.read_bytes()
        occupied = self.tmp / "occupied"
        occupied.mkdir()
        (occupied / "other.txt").write_text("Fictional notes", encoding="utf-8")
        self.call("--store", str(occupied), "init", "--remember", status=1, use_default=True)
        self.assertEqual(self.settings.read_bytes(), before)

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_remember_git_target_and_branch(self):
        repository = self.tmp / "fictional.git"
        subprocess.run(
            ["git", "init", "--bare", "--quiet", str(repository)], check=True, capture_output=True
        )
        address = f"git+{repository.as_uri()}"
        initialized = json.loads(
            self.call(
                "--store",
                address,
                "--git-branch",
                "notes",
                "init",
                "--remember",
                "--json",
                use_default=True,
            )
        )
        state = json.loads(self.call("validate", "--json", use_default=True))
        self.assertEqual(state["workspace_id"], initialized["workspace_id"])
        active = json.loads(self.call("config", "--json", use_default=True))
        self.assertEqual(active["store"], address)
        self.assertEqual(active["git_branch"], "notes")

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
