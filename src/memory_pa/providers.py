"""Bounded, read-only access to documented note-taking APIs."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import MemoryPAError
from .files import parse_json, private_path

APIS = {
    "granola": "https://public-api.granola.ai/v1/notes",
    "pocket": "https://public.heypocketai.com/api/v1/public/recordings",
}
MAX_RESPONSE = 16 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _key_path(provider: str) -> Path:
    if provider not in APIS:
        raise MemoryPAError("Use an API key for Granola or Pocket.")
    return private_path(Path.home() / ".memory-pa" / "keys") / provider


def _valid_key(key: str) -> str:
    if not re.fullmatch(r"[!-~]{12,4096}", key):
        raise MemoryPAError("Paste a single API key from the provider's settings.")
    return key


def _get_key(provider: str) -> str:
    environment = f"MEMORY_PA_{provider.upper()}_API_KEY"
    key = os.environ.get(environment)
    if key is not None:
        return _valid_key(key)
    source = _key_path(provider)
    if source.is_symlink() or (source.exists() and not source.is_file()):
        raise MemoryPAError("The local API key must be stored in a regular file.")
    if not source.exists():
        raise MemoryPAError(
            f"Run memory-pa connect {provider} in your terminal, or set {environment} as a secret."
        )
    if os.name == "posix" and source.stat().st_mode & 0o077:
        raise MemoryPAError(
            f"Restrict the key file to your account or run memory-pa connect {provider} again."
        )
    with source.open(encoding="ascii") as stream:
        return _valid_key(stream.read(4097))


def connect(provider: str, key: str) -> None:
    key = _valid_key(key.strip())
    path = _key_path(provider)
    fetch(provider, limit=1, key=key)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".key-") as temporary:
        stage = Path(temporary, "key")
        with os.fdopen(
            os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="ascii"
        ) as stream:
            stream.write(key)
        stage.replace(path)


def disconnect(provider: str) -> None:
    _key_path(provider).unlink(missing_ok=True)


def _get(url, params, key):
    request = Request(
        f"{url}?{urlencode(params)}" if params else url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "memory-pa/0.1",
        },
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            message = (
                "The note taker denied access. Check your key, plan, and the notes it can read."
            )
        elif exc.code == 404:
            message = "The note taker could not find that record. Check its ID and your access."
        elif exc.code == 429:
            message = (
                "The note taker is rate limiting requests. Try again later with the same window."
            )
        else:
            message = f"The note taker returned HTTP {exc.code}."
        exc.close()
        raise MemoryPAError(message) from exc
    except (URLError, OSError) as exc:
        raise MemoryPAError(
            "Could not reach the note taker. Check your network and try again."
        ) from exc
    if len(body) > MAX_RESPONSE:
        raise MemoryPAError(
            "The note taker's response is too large. Try a smaller page or select an excerpt in the provider."
        )
    value = parse_json(body, "the note taker response")
    if not isinstance(value, dict):
        raise MemoryPAError("Unexpected response from the note taker.")
    return value


def _metadata(record):
    if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
        raise MemoryPAError("A note taker record is missing its ID.")
    return {
        key: record[key]
        for key in ("id", "title", "created_at", "updated_at", "recording_at", "web_url", "state")
        if isinstance(record.get(key), str)
    }


def _page_token(provider, value):
    if provider == "granola":
        more, token = value.get("hasMore"), value.get("cursor")
        if more is False or more is True and isinstance(token, str) and token:
            return token if more else None
    else:
        page = value.get("pagination")
        if isinstance(page, dict):
            more, number = page.get("has_more"), page.get("page")
            if more is False:
                return None
            if more is True and type(number) is int and number >= 1:
                return str(number + 1)
    raise MemoryPAError("The note taker returned invalid pagination data.")


def _list_records(provider, key, since, until, limit, token):
    if provider == "granola":
        before = None
        if until:
            try:
                before = (date.fromisoformat(until) + timedelta(days=1)).isoformat()
            except OverflowError as exc:
                raise MemoryPAError("Choose a Granola end date before 9999-12-31.") from exc
        params = {
            "page_size": limit,
            "created_after": since,
            "created_before": before,
            "cursor": token,
        }
        field = "notes"
    else:
        if token and not re.fullmatch(r"[1-9]\d{0,7}", token, flags=re.ASCII):
            raise MemoryPAError("Pocket expects a positive page number from next_page.")
        params = {"limit": limit, "start_date": since, "end_date": until, "page": token}
        field = "data"
    value = _get(
        APIS[provider], {name: item for name, item in params.items() if item is not None}, key
    )
    items = value.get(field)
    if not isinstance(items, list) or len(items) > limit:
        raise MemoryPAError("The note taker returned an unexpected list of records.")
    return {
        "provider": provider,
        "records": [_metadata(item) for item in items],
        "next_page": _page_token(provider, value),
    }


def _fetch_record(provider, key, record, transcript, limit, token):
    url = f"{APIS[provider]}/{record}"
    if provider == "granola" and transcript:
        params = {"page_size": limit}
        if token:
            params["cursor"] = token
        value = _get(f"{url}/transcript", params, key)
        segments = value.get("transcript")
        if not isinstance(segments, list):
            raise MemoryPAError("Granola did not supply transcript text for this note.")
        return {
            "provider": provider,
            "id": record,
            "transcript": segments,
            "next_page": _page_token(provider, value),
        }
    if token:
        raise MemoryPAError("Use --page-token with a list or a Granola transcript.")
    params = (
        {"include_transcript": "true" if transcript else "false"} if provider == "pocket" else {}
    )
    value = _get(url, params, key)
    item = value.get("data") if provider == "pocket" else value
    metadata = _metadata(item)
    if metadata["id"] != record:
        raise MemoryPAError("The note taker returned a different record ID.")
    if provider == "pocket":
        content = {"summary": item.get("summarizations")}
        if transcript:
            content["transcript"] = item.get("transcript")
    else:
        content = {"summary": item.get("summary_markdown") or item.get("summary_text")}
    return {"provider": provider, **metadata, **content}


def fetch(
    provider,
    *,
    record=None,
    since=None,
    until=None,
    limit=10,
    token=None,
    transcript=False,
    key=None,
):
    if provider not in APIS:
        raise MemoryPAError("The built-in API readers support Granola and Pocket.")
    if not 1 <= limit <= 30:
        raise MemoryPAError("Choose a page size between 1 and 30.")
    if token and (len(token) > 4096 or any(ord(character) < 32 for character in token)):
        raise MemoryPAError("Use the next_page value from the note taker response.")
    if record is not None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,199}", record):
            raise MemoryPAError("Use a record ID returned by the note taker.")
        if since or until:
            raise MemoryPAError("Use dates when listing records, or --id for a single record.")
        return _fetch_record(provider, key or _get_key(provider), record, transcript, limit, token)
    if transcript:
        raise MemoryPAError("Use --id to read a transcript for one record.")
    for day in (since, until):
        if day and (not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) or not _is_date(day)):
            raise MemoryPAError("Use YYYY-MM-DD for the date window.")
    if since and until and since > until:
        raise MemoryPAError("The start date must come before or match the end date.")
    return _list_records(provider, key or _get_key(provider), since, until, limit, token)


def _is_date(day):
    try:
        date.fromisoformat(day)
    except ValueError:
        return False
    return True
