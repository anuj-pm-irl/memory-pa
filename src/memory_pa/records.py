from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from importlib.resources import files
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .errors import MemoryPAError
from .files import digest, parse_json

PROPOSAL_ID = "urn:memory-pa:proposal:v1"
WORKSPACE_ID = "urn:memory-pa:workspace:v1"
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]")
SCHEMAS = Registry().with_resources(
    (
        key,
        Resource.from_contents(
            parse_json(files("memory_pa.schemas").joinpath(name).read_bytes(), name)
        ),
    )
    for key, name in ((PROPOSAL_ID, "proposal-v1.json"), (WORKSPACE_ID, "workspace-v1.json"))
)


def validator(reference):
    return Draft202012Validator(
        {"$ref": reference}, registry=SCHEMAS, format_checker=Draft202012Validator.FORMAT_CHECKER
    )


VALIDATORS = {"proposal": validator(PROPOSAL_ID)}
VALIDATORS.update(
    {kind: validator(f"{WORKSPACE_ID}#/$defs/{kind}") for kind in ("workspace", "source", "entity")}
)


def validate_record(kind, value) -> None:
    if (
        kind in {"workspace", "proposal"}
        and isinstance(value, dict)
        and type(value.get("format_version")) is not int
    ):
        raise MemoryPAError(f"The {kind} requires an integer format_version of 1.")
    if (
        kind in {"workspace", "proposal"}
        and isinstance(value, dict)
        and value.get("format_version") != 1
    ):
        raise MemoryPAError(f"Unsupported {kind} format version. This release supports v1.")
    failure = next(VALIDATORS[kind].iter_errors(value), None)
    if failure:
        field = ".".join(str(key) for key in failure.absolute_path) or "root"
        raise MemoryPAError(f"Invalid {kind} field {field} ({failure.validator}).")
    _check_text(value)
    if kind in {"source", "proposal"}:
        origin = value["origin" if kind == "source" else "source"]
        if origin.get("url"):
            link = urlsplit(origin["url"])
            if not link.hostname or link.username is not None:
                raise MemoryPAError("Source links must use HTTP(S) without embedded credentials.")
    if kind == "source":
        try:
            datetime.fromisoformat(value["captured_at"])
        except ValueError as exc:
            raise MemoryPAError("Invalid source capture time.") from exc


def _check_text(value) -> None:
    if isinstance(value, str):
        check_text(value)
    if isinstance(value, dict):
        for item in value.values():
            _check_text(item)
    if isinstance(value, list):
        for item in value:
            _check_text(item)


def check_text(value: str) -> None:
    if CONTROL_CHARACTERS.search(value):
        raise MemoryPAError(
            "Text must be valid Unicode without control characters other than tabs and line breaks."
        )
    if value and not value.strip():
        raise MemoryPAError("Text fields must contain something besides whitespace.")


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def fingerprint(text: str) -> str:
    return digest(normalize(text).encode("utf-8"))


def source_key(origin, text_fingerprint):
    external = origin.get("external")
    if external:
        return ("external", external["provider"], external["account"], external["id"])
    return ("text", origin["kind"], text_fingerprint)


def note_stem(title: str, date: str | None) -> str:
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:55].rstrip("-")
    if not slug:
        slug = "note-" + fingerprint(title)[:8]
    return f"{slug}-{date or 'undated'}"
