from __future__ import annotations

import re
import uuid
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from .errors import MemoryPAError, ReviewRequired
from .files import check_tree, digest, json_bytes, parse_json
from .records import (
    check_text,
    fingerprint,
    normalize,
    note_stem,
    source_key,
    validate_record,
)
from .render import action_text, navigation, note_prefix

MAX_SOURCE_BYTES = 2 * 1024 * 1024


def empty_workspace() -> dict[str, bytes]:
    return {
        "workspace.json": json_bytes({"format_version": 1, "workspace_id": uuid.uuid4().hex}),
        **navigation({}, {}),
    }


def _label(source):
    return {"source_id": source["id"], "note": source["note"], "title": source["title"]}


def _title_key(title, date):
    return normalize(title).casefold(), date


def _actions(sources):
    history = defaultdict(dict)
    for item in sources.values():
        for action in item["actions"]:
            chain = history[action["id"]]
            if item["id"] in chain:
                raise MemoryPAError("An action can be updated only once per source.")
            chain[item["id"]] = (action, item)
    current = {}
    for action_id, chain in history.items():
        parents = {action["previous_source"] for action, _ in chain.values()}
        heads = chain.keys() - parents
        if len(heads) != 1:
            raise MemoryPAError("An action must have one current state.")
        cursor = next(iter(heads))
        current[action_id] = chain[cursor]
        visited = set()
        topic = chain[cursor][1]["topic"]
        while cursor is not None:
            if cursor not in chain or cursor in visited or chain[cursor][1]["topic"] != topic:
                raise MemoryPAError("Invalid action history link.")
            visited.add(cursor)
            cursor = chain[cursor][0]["previous_source"]
        if len(visited) != len(chain):
            raise MemoryPAError("An action history must be a single chain.")
    return current


@dataclass(frozen=True)
class Capture:
    source: dict
    files: dict[str, bytes] | None


class Workspace:
    def __init__(self, files: Mapping[str, bytes]):
        check_tree(files)
        self.files = dict(files)
        manifest = self._record("workspace.json", "workspace")
        self.id = manifest["workspace_id"]
        self.sources = self._records("sources", "source")
        self.entities = self._records("entities", "entity")
        self.source_keys = {}
        self.titles = {}
        self.by_path = {}
        self.text = {}
        self._read_notes()
        self._check_entity_links()
        self.actions = _actions(self.sources)
        views = navigation(self.sources, self.actions)
        if any(self.files.get(name) != content for name, content in views.items()):
            raise MemoryPAError("The index or topic summaries are missing or out of date.")
        expected_paths = {
            "workspace.json",
            *views,
            *self.by_path,
            *(f"sources/{key}.json" for key in self.sources),
            *(f"entities/{key}.json" for key in self.entities),
        }
        if self.files.keys() != expected_paths:
            raise MemoryPAError("The workspace contains unrecognized files.")

    def _record(self, path, kind):
        raw = self.files.get(path)
        if raw is None:
            raise MemoryPAError(f"The workspace is missing {path}.")
        record = parse_json(raw, path)
        validate_record(kind, record)
        return record

    def _records(self, folder, kind):
        records = {}
        for name in self.files:
            if name.startswith(f"{folder}/"):
                record = self._record(name, kind)
                if name != f"{folder}/{record['id']}.json":
                    raise MemoryPAError(f"A {kind} filename must match its ID.")
                records[record["id"]] = record
        return records

    def _read_notes(self):
        for source in self.sources.values():
            source_id = source["id"]
            path = source["note"]
            stem = f"topics/{source['topic']}/{note_stem(source['title'], source['date'])}"
            if path not in (f"{stem}.md", f"{stem}-{source_id[-8:]}.md") or path in self.by_path:
                raise MemoryPAError("A note path must match its topic, date, title, and source.")
            content = self.files.get(path, b"")
            prefix = note_prefix(source)
            if not content.startswith(prefix):
                raise MemoryPAError(
                    "A note is missing or its structured sections differ from its source record."
                )
            body = content[len(prefix) :]
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MemoryPAError("Note source text must use UTF-8.") from exc
            check_text(text)
            if (
                not text.strip()
                or len(body) > MAX_SOURCE_BYTES
                or digest(body) != source["text_sha256"]
            ):
                raise MemoryPAError(
                    "A note does not match its original source text digest or size limit."
                )
            if fingerprint(text) != source["fingerprint"]:
                raise MemoryPAError("The note fingerprint does not match its source record.")
            key = source_key(source["origin"], source["fingerprint"])
            title = _title_key(source["title"], source["date"])
            if key in self.source_keys or title in self.titles:
                raise MemoryPAError(
                    "The workspace contains duplicate source keys or titles and dates."
                )
            self.source_keys[key] = source
            self.titles[title] = source
            self.by_path[path] = source
            self.text[source_id] = text

    def _check_entity_links(self):
        links = defaultdict(set)
        for entity in self.entities.values():
            if entity["mentions"][0]["name"] != entity["name"]:
                raise MemoryPAError("An entity's name must match its first mention.")
            for index, mention in enumerate(entity["mentions"]):
                source_id = mention["source_id"]
                if source_id not in self.sources or entity["id"] in links[source_id]:
                    raise MemoryPAError("An entity mention must cite a distinct existing note.")
                if index and "basis" not in mention:
                    raise MemoryPAError("A linked entity mention needs a source-backed basis.")
                links[source_id].add(entity["id"])
        if any(set(source["entities"]) != links[source["id"]] for source in self.sources.values()):
            raise MemoryPAError("Entity links and their source references disagree.")

    def _id(self, kind, key) -> str:
        return f"{kind}-{uuid.uuid5(uuid.UUID(hex=self.id), key).hex}"

    def prepare(self, proposal) -> Capture:
        validate_record("proposal", proposal)
        body = proposal["text"].encode("utf-8")
        if len(body) > MAX_SOURCE_BYTES:
            raise MemoryPAError("The selected source text must fit in 2 MiB of UTF-8.")
        text_hash = fingerprint(proposal["text"])
        origin = proposal["source"]
        key = source_key(origin, text_hash)
        existing = self.source_keys.get(key)
        if existing:
            if existing["fingerprint"] != text_hash:
                raise ReviewRequired(
                    "This provider record already has different source text. Review the original note first.",
                    [_label(existing)],
                )
            return Capture(existing, None)

        title = proposal["title"].strip()
        date = proposal.get("date")
        existing = self.titles.get(_title_key(title, date))
        if existing:
            raise ReviewRequired(
                "This title and date already have a note with different source text. Review it before saving a separate note.",
                [_label(existing)],
            )

        topic = proposal["topic"]
        source_id = self._id("src", json_bytes(key).decode("utf-8"))
        stem = f"topics/{topic}/{note_stem(title, date)}"
        path = f"{stem}.md"
        if path in self.files:
            path = f"{stem}-{source_id[-8:]}.md"
        if source_id in self.sources or path in self.files:
            raise MemoryPAError("The new note would reuse an existing ID or path.")
        source = {
            "id": source_id,
            "topic": topic,
            "title": title,
            "date": date,
            "captured_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "origin": origin,
            "note": path,
            "text_sha256": digest(body),
            "fingerprint": text_hash,
            "summary": proposal.get("summary", ""),
            "decisions": proposal.get("decisions", []),
            "actions": list(self._new_actions(source_id, topic, date, proposal.get("actions", []))),
            "entities": [],
        }
        entities = self._new_mentions(source_id, proposal.get("entities", []))
        source["entities"] = list(entities)
        combined = {**self.sources, source_id: source}
        files = {
            **self.files,
            **navigation(combined, _actions(combined)),
            f"sources/{source_id}.json": json_bytes(source),
            path: note_prefix(source) + body,
            **{f"entities/{key}.json": json_bytes(entity) for key, entity in entities.items()},
        }
        Workspace(files)
        return Capture(source, files)

    def _new_actions(self, source_id, topic, date, proposals):
        for position, proposal in enumerate(proposals):
            action_id = proposal.get("id")
            if action_id:
                state = self.actions.get(action_id)
                if state is None or state[1]["topic"] != topic:
                    raise ReviewRequired("Choose an existing action ID from this topic.")
                previous, evidence = state
                if date and evidence["date"] and date < evidence["date"]:
                    raise ReviewRequired(
                        "This note predates the current action state. Review its evidence first.",
                        [_label(evidence)],
                    )
                yield {**previous, **proposal, "previous_source": evidence["id"]}
            else:
                yield {
                    "id": self._id("act", f"{source_id}:{position}"),
                    "owner": None,
                    "due": None,
                    "status": "open",
                    "previous_source": None,
                    **proposal,
                }

    def _new_mentions(self, source_id, proposals):
        changes = {}
        for position, proposal in enumerate(proposals):
            name = proposal["name"].strip()
            kind = proposal["kind"]
            entity_id = proposal.get("id")
            mention = {"source_id": source_id, "name": name, "facts": proposal.get("facts", [])}
            if entity_id:
                existing = self.entities.get(entity_id)
                if existing is None or existing["kind"] != kind or entity_id in changes:
                    raise ReviewRequired(
                        "Choose one existing entity of the same kind for each mention."
                    )
                entity = deepcopy(existing)
                mention["basis"] = proposal["basis"]
            else:
                candidates = [
                    {"id": entity["id"], "name": entity["name"], "kind": kind}
                    for entity in (self.entities | changes).values()
                    if entity["kind"] == kind
                    and any(
                        normalize(item["name"]).casefold() == normalize(name).casefold()
                        for item in entity["mentions"]
                    )
                ]
                if candidates and not proposal.get("distinct"):
                    raise ReviewRequired(
                        "This entity name has possible matches. Link by ID with evidence or confirm a distinct entity.",
                        candidates,
                    )
                entity_id = self._id("ent", f"{source_id}:{position}")
                entity = {"id": entity_id, "name": name, "kind": kind, "mentions": []}
            entity["mentions"].append(mention)
            changes[entity_id] = entity
        return changes

    def _sections(self, source):
        yield "title", source["title"]
        yield "summary", source["summary"]
        for decision in source["decisions"]:
            yield "decisions", decision
        for action in source["actions"]:
            yield "action-items", f"{action_text(action)} ({action['status']}) [{action['id']}]"
        for entity_id in source["entities"]:
            entity = self.entities[entity_id]
            mention = next(item for item in entity["mentions"] if item["source_id"] == source["id"])
            yield (
                "entities",
                f"{mention['name']} ({entity['kind']}) [{entity_id}] "
                + " · ".join(mention["facts"]),
            )
        yield "source-text", self.text[source["id"]]

    def search(self, query: str, limit: int) -> list[dict]:
        terms = set(re.findall(r"\w+", query.casefold()))
        if not terms:
            raise MemoryPAError("Enter at least one word to search for.")
        sources = sorted(
            self.sources.values(),
            key=lambda item: (item["date"] or "", item["captured_at"], item["id"]),
            reverse=True,
        )
        results = []
        for source in sources:
            for section, text in self._sections(source):
                flat = normalize(text)
                folded = flat.casefold()
                if all(term in folded for term in terms):
                    start = max(0, min(folded.index(term) for term in terms) - 44)
                    excerpt = flat[start : start + 260]
                    if start:
                        excerpt = "…" + excerpt
                    if start + 260 < len(flat):
                        excerpt += "…"
                    results.append(
                        {
                            **_label(source),
                            "date": source["date"],
                            "section": section,
                            "text": excerpt,
                        }
                    )
                    if len(results) == limit:
                        return results
        return results

    def show(self, selector: str, section: str | None) -> bytes:
        source = self.sources.get(selector) or self.by_path.get(selector)
        if section:
            if source is None:
                raise MemoryPAError("Choose a source ID or a note path to open a section.")
            if section == "source-text":
                return self.text[source["id"]].encode("utf-8")
            return (
                "\n".join(text for name, text in self._sections(source) if name == section) + "\n"
            ).encode("utf-8")
        path = source["note"] if source else selector
        if selector in self.entities:
            path = f"entities/{selector}.json"
        if path not in self.files:
            raise MemoryPAError("No memory file or ID matched. Try search or open index.md.")
        return self.files[path]
