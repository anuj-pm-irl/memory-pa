import json
import unittest
from copy import deepcopy
from importlib.resources import files

from memory_pa.errors import MemoryPAError, ReviewRequired
from memory_pa.files import json_bytes, parse_json
from memory_pa.memory import Workspace, empty_workspace


def example():
    return json.loads(files("memory_pa.examples").joinpath("robot-club.json").read_bytes())


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.proposal = example()
        self.original = Workspace(empty_workspace())
        self.capture = self.original.prepare(self.proposal)
        self.workspace = Workspace(self.capture.files)

    def test_recall_with_evidence(self):
        results = self.workspace.search("blue lantern", 10)
        self.assertIn("decisions", {hit["section"] for hit in results})
        self.assertIn("action-items", {hit["section"] for hit in results})
        self.assertTrue(all(hit["note"] == self.capture.source["note"] for hit in results))
        self.assertEqual(
            self.workspace.show(self.capture.source["id"], "source-text"),
            self.proposal["text"].encode(),
        )
        self.assertIn(b"Kit Copper", self.workspace.show("topics/robot-club/_summary.md", None))

    def test_exact_repeat_preserves_note_and_review_uses_original(self):
        similar = deepcopy(self.proposal)
        similar["text"] = "\r\n" + similar["text"].replace(" ", "  ")
        duplicate = self.workspace.prepare(similar)
        self.assertIsNone(duplicate.files)
        self.assertEqual(duplicate.source["id"], self.capture.source["id"])
        similar["text"] = "The club should use a purple light."
        with self.assertRaises(ReviewRequired) as review:
            self.workspace.prepare(similar)
        self.assertEqual(review.exception.candidates[0]["note"], self.capture.source["note"])

    def test_provider_identity_is_scoped_to_account(self):
        source = {
            "kind": "recording",
            "external": {"provider": "sample-recorder", "account": "first", "id": "fixture-001"},
        }
        first = self.original.prepare({**self.proposal, "source": source})
        workspace = Workspace(first.files)
        revised = {
            **self.proposal,
            "source": source,
            "text": "A provider changed what was recorded.",
        }
        with self.assertRaises(ReviewRequired):
            workspace.prepare(revised)
        separate = deepcopy(revised)
        separate["source"]["external"]["account"] = "second"
        separate["title"] = "Another club meeting"
        separate["entities"] = []
        self.assertIsNotNone(workspace.prepare(separate).files)

    def test_unresolved_names_and_explicit_links(self):
        identity = self.capture.source["entities"][0]
        follow_up = {
            "format_version": 1,
            "topic": "robot-club",
            "title": "Lantern follow-up",
            "source": {"kind": "email"},
            "date": "2026-02-04",
            "text": "Kit Copper tested the blue lantern.",
            "entities": [
                {"kind": "person", "name": "Kit Copper", "facts": ["Tested the lantern."]}
            ],
        }
        with self.assertRaises(ReviewRequired) as review:
            self.workspace.prepare(follow_up)
        self.assertEqual(review.exception.candidates[0]["id"], identity)
        follow_up["entities"][0].update(
            {
                "id": identity,
                "basis": "The club confirmed this was the volunteer from its prior meeting.",
            }
        )
        linked = self.workspace.prepare(follow_up)
        state = Workspace(linked.files)
        self.assertEqual(len(state.entities[identity]["mentions"]), 2)
        self.assertEqual(
            self.workspace.show(self.capture.source["note"], None),
            state.show(self.capture.source["note"], None),
        )

    def test_open_actions_carry_forward_and_keep_history_on_completion(self):
        action = self.capture.source["actions"][0]
        proposal = {
            "format_version": 1,
            "topic": "robot-club",
            "title": "Lantern update",
            "date": "2026-02-04",
            "source": {"kind": "chat"},
            "text": "The blue lantern passed its test.",
        }
        stable = Workspace(self.workspace.prepare(proposal).files)
        summary = "topics/robot-club/_summary.md"
        self.assertIn(action["id"].encode(), stable.show(summary, None))
        proposal["actions"] = [{"id": action["id"], "status": "done"}]
        changed = Workspace(self.workspace.prepare(proposal).files)
        self.assertNotIn(action["id"].encode(), changed.show(summary, None))
        self.assertEqual(changed.actions[action["id"]][0]["status"], "done")
        self.assertEqual(
            changed.actions[action["id"]][0]["previous_source"], self.capture.source["id"]
        )
        self.assertIn(b"(open)", changed.show(self.capture.source["note"], None))

    def test_capture_unknown_date_and_verbatim_utf8(self):
        note = {
            "format_version": 1,
            "topic": "examples",
            "title": "An undated note",
            "source": {"kind": "file"},
            "text": "\r\nUn caf\u00e9.\r\n  ",
        }
        saved = self.original.prepare(note)
        self.assertTrue(saved.source["note"].endswith("-undated.md"))
        self.assertIsNone(saved.source["date"])
        self.assertEqual(
            Workspace(saved.files).show(saved.source["note"], "source-text"), note["text"].encode()
        )

    def test_validate_rejects_corruption_and_future_versions(self):
        original = self.capture.files
        version = parse_json(original["workspace.json"], "test")
        for damaged in (
            {**original, "workspace.json": json_bytes({**version, "format_version": 2})},
            {**original, "index.md": b"Stale index"},
            {**original, self.capture.source["note"]: original[self.capture.source["note"]] + b"!"},
            {**original, "untracked.md": b"Unexpected file"},
            {**original, "../wrong.md": b"Invalid path"},
        ):
            with self.subTest(paths=damaged.keys()), self.assertRaises(MemoryPAError):
                Workspace(damaged)

    def test_invalid_proposals_are_rejected(self):
        for update in (
            {"format_version": 2},
            {"date": "2026-02-31"},
            {"text": "\x1b[31m"},
            {"title": " "},
        ):
            with self.subTest(update=update), self.assertRaises(MemoryPAError):
                self.original.prepare({**self.proposal, **update})
