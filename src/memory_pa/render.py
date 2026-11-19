from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from .records import normalize


def inline(text: str) -> str:
    return (
        normalize(text)
        .replace("\\", "\\\\")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace("#", r"\#")
    )


def action_text(action) -> str:
    parts = [action["text"]]
    if action["owner"]:
        parts.append(f"owner {action['owner']}")
    if action["due"]:
        parts.append(f"due {action['due']}")
    return " · ".join(parts)


def bullets(values) -> str:
    return "\n".join(f"- {inline(value)}" for value in values) or "None recorded."


def note_prefix(source) -> bytes:
    actions = [f"{action_text(action)} ({action['status']})" for action in source["actions"]]
    entities = "\n".join(
        f"- [{entity}](../../entities/{entity}.json)" for entity in source["entities"]
    )
    return (
        f"# {inline(source['title'])}\n\n"
        f"- **Date** {source['date'] or 'Unknown'}\n"
        f"- **Topic** {source['topic']}\n"
        f"- **Source** `{source['id']}`\n\n"
        f"## Summary\n\n{inline(source['summary']) or 'None recorded.'}\n\n"
        f"## Decisions\n\n{bullets(source['decisions'])}\n\n"
        f"## Action items\n\n{bullets(actions)}\n\n"
        f"## Entities\n\n{entities or 'None recorded.'}\n\n"
        "## Source text\n\n"
    ).encode()


def _source_link(source, section="") -> str:
    name = PurePosixPath(source["note"]).name
    return f"[{inline(source['title'])}]({name}{section})"


def _order(source):
    return (source["date"] or "", source["captured_at"], source["id"])


def navigation(sources, actions) -> dict[str, bytes]:
    groups = defaultdict(list)
    for source in sources.values():
        groups[source["topic"]].append(source)
    open_actions = defaultdict(list)
    for action, source in actions.values():
        if action["status"] == "open":
            open_actions[source["topic"]].append((action, source))
    pages = {}
    index = ["# Memory index", ""]
    for topic, notes in sorted(groups.items()):
        path = f"topics/{topic}/_summary.md"
        index.append(f"- [{topic}]({path}) · {len(notes)} {'note' if len(notes) == 1 else 'notes'}")
        ordered = sorted(notes, key=_order, reverse=True)
        recent = [
            f"- {inline(item['summary'])} · {_source_link(item, '#summary')}"
            for item in ordered
            if item["summary"]
        ][:5]
        tasks = [
            f"- [ ] {inline(action_text(action))} · {_source_link(source, '#action-items')} · `{action['id']}`"
            for action, source in sorted(
                open_actions[topic],
                key=lambda item: (item[0]["due"] or "9999-12-31", item[0]["id"]),
            )
        ]
        decisions = [
            f"- {inline(decision)} · {_source_link(source, '#decisions')}"
            for source in ordered
            for decision in source["decisions"]
        ]
        links = [f"- {source['date'] or 'Undated'} · {_source_link(source)}" for source in ordered]
        lines = [f"# {topic}", ""]
        for heading, entries in (
            ("Recent notes", recent),
            ("Open actions", tasks),
            ("Decisions", decisions),
            ("Notes", links),
        ):
            lines.extend([f"## {heading}", "", *(entries or ["None recorded."]), ""])
        pages[path] = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
    if not groups:
        index.append("Your first note will appear here.")
    pages["index.md"] = ("\n".join(index) + "\n").encode("utf-8")
    return pages
