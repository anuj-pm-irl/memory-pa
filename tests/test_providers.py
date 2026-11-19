import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from memory_pa.errors import MemoryPAError
from memory_pa.providers import _get, connect, disconnect, fetch

KEY = "fictional-test-only"


class ProviderTests(unittest.TestCase):
    def test_granola_list_uses_window_and_cursor(self):
        response = {
            "notes": [
                {
                    "id": "not_fixture",
                    "title": "Planting day",
                    "owner": {"email": "sample@example.test"},
                }
            ],
            "hasMore": True,
            "cursor": "next-fixture",
        }
        with patch("memory_pa.providers._get", return_value=response) as request:
            result = fetch(
                "granola",
                since="2026-02-01",
                until="2026-02-04",
                limit=3,
                token="previous",
                key=KEY,
            )
        request.assert_called_once_with(
            "https://public-api.granola.ai/v1/notes",
            {
                "page_size": 3,
                "created_after": "2026-02-01",
                "created_before": "2026-02-05",
                "cursor": "previous",
            },
            KEY,
        )
        self.assertEqual(result["records"], [{"id": "not_fixture", "title": "Planting day"}])
        self.assertEqual(result["next_page"], "next-fixture")

    def test_granola_transcript_has_its_own_pagination(self):
        response = {
            "transcript": [{"text": "A blue lantern.", "speaker": {"source": "speaker"}}],
            "hasMore": False,
            "cursor": None,
        }
        with patch("memory_pa.providers._get", return_value=response) as request:
            result = fetch("granola", record="not_fixture", transcript=True, key=KEY)
        request.assert_called_once_with(
            "https://public-api.granola.ai/v1/notes/not_fixture/transcript", {"page_size": 10}, KEY
        )
        self.assertIsNone(result["next_page"])
        self.assertEqual(result["transcript"], response["transcript"])

    def test_pocket_list_uses_its_documented_pagination(self):
        response = {
            "data": [{"id": "fixture", "title": "Lamp check"}],
            "pagination": {"has_more": True, "page": 2},
        }
        with patch("memory_pa.providers._get", return_value=response) as request:
            result = fetch("pocket", since="2026-02-01", token="2", key=KEY)
        request.assert_called_once_with(
            "https://public.heypocketai.com/api/v1/public/recordings",
            {"limit": 10, "start_date": "2026-02-01", "page": "2"},
            KEY,
        )
        self.assertEqual(result["next_page"], "3")

    def test_pocket_detail_copies_selected_fields(self):
        response = {
            "data": {
                "id": "fixture",
                "title": "Lamp check",
                "audio_url": "https://example.test/audio",
                "transcript": {"segments": [{"text": "Tested."}]},
            }
        }
        with patch("memory_pa.providers._get", return_value=response) as request:
            result = fetch("pocket", record="fixture", transcript=True, key=KEY)
        request.assert_called_once_with(
            "https://public.heypocketai.com/api/v1/public/recordings/fixture",
            {"include_transcript": "true"},
            KEY,
        )
        self.assertEqual(result["transcript"], response["data"]["transcript"])
        self.assertNotIn("audio_url", result)

    def test_connection_uses_a_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory, "keys", "pocket")
            with (
                patch("memory_pa.providers._key_path", return_value=key_path),
                patch(
                    "memory_pa.providers._get",
                    return_value={"data": [], "pagination": {"has_more": False}},
                ),
            ):
                connect("pocket", KEY)
                self.assertEqual(key_path.read_text(), KEY)
                if os.name == "posix":
                    self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(fetch("pocket")["records"], [])
                disconnect("pocket")
                self.assertFalse(key_path.exists())

    def test_fetch_validates_before_reading_credentials(self):
        for kwargs in ({"record": "../bad"}, {"since": "2026-02-31"}, {"limit": 31}):
            with self.subTest(kwargs=kwargs), self.assertRaises(MemoryPAError):
                fetch("pocket", **kwargs)

    def test_http_error_hides_credentials_and_response(self):
        error = HTTPError(
            "https://public-api.granola.ai/v1/notes",
            401,
            "Unauthorized",
            {},
            io.BytesIO(KEY.encode()),
        )
        with patch("memory_pa.providers.build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(MemoryPAError) as caught:
                _get("https://public-api.granola.ai/v1/notes", {}, KEY)
        self.assertIn("denied access", str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))
