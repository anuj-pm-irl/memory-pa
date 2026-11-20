from __future__ import annotations

import argparse
import getpass
import sys
import tempfile
import warnings
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

from . import providers
from .errors import Conflict, MemoryPAError, ReviewRequired, UncertainWrite
from .files import (
    MAX_FILE_BYTES,
    digest,
    export_tree,
    json_bytes,
    parse_json,
    read_tree,
)
from .memory import MAX_SOURCE_BYTES, Workspace, empty_workspace
from .settings import remember, select_store, settings_data
from .storage import open_storage
from .storage.local import LocalStorage

SECTIONS = ("title", "summary", "decisions", "action-items", "entities", "source-text")


def _read(name, maximum):
    if name == "-":
        content = sys.stdin.buffer.read(maximum + 1)
    else:
        with Path(name).expanduser().open("rb") as stream:
            content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise MemoryPAError("The input exceeds the v1 size limit. Select a smaller excerpt.")
    return content


def _proposal(args):
    if args.proposal:
        if args.topic or args.title or args.date:
            raise MemoryPAError("Set the title, date, and topic inside the JSON proposal.")
        return parse_json(_read(args.proposal, MAX_FILE_BYTES), "the proposal")
    if not args.title or not args.topic:
        raise MemoryPAError("Give the note a --title and a --topic when using --file.")
    return {
        "format_version": 1,
        "topic": args.topic,
        "title": args.title,
        "date": args.date,
        "source": {"kind": "note" if args.file == "-" else "file"},
        "text": _read(args.file, MAX_SOURCE_BYTES).decode("utf-8"),
    }


def _error_json(exc) -> dict:
    response = {"status": exc.status, "message": str(exc)}
    if isinstance(exc, ReviewRequired):
        response["candidates"] = exc.candidates
    return response


def _output(args, data, lines=()):
    if args.json:
        print(json_bytes(data).decode("utf-8"), end="")
    else:
        for line in lines:
            print(line)


def _add(args, store, head, workspace, selection):
    proposal = _proposal(args)
    capture = workspace.prepare(proposal)
    source = capture.source
    result = {"source_id": source["id"], "note": source["note"], "revision": head.token}
    if capture.files is None:
        _output(args, {"status": "duplicate", **result}, [f"Already saved in {source['note']}."])
        return
    review = [workspace.id, head.token, selection.store, selection.git_branch, proposal]
    if selection.aws_profile:
        review.append(selection.aws_profile)
    apply_token = digest(json_bytes(review))
    if args.apply is None:
        changes = sorted(
            path for path, body in capture.files.items() if workspace.files.get(path) != body
        )
        preview = {
            "status": "ready",
            "apply_token": apply_token,
            "changed_paths": changes,
            **result,
        }
        _output(
            args,
            preview,
            [
                f"Ready to save {source['note']}",
                *(f"  {path}" for path in changes),
                f"Run the same command with --apply {apply_token} to save.",
            ],
        )
        return
    if args.apply != apply_token:
        raise Conflict("The workspace, destination, or proposal changed. Preview the note again.")
    result["revision"] = store.publish(head.token, capture.files)
    _output(args, {"status": "saved", **result}, [f"Saved {source['note']}."])


def _init(args, store, head, selection):
    defaults = None
    if args.remember:
        target = str(store.root) if isinstance(store, LocalStorage) else selection.store
        defaults = settings_data(target, selection.git_branch, selection.aws_profile)
    seed = read_tree(Path(args.seed).expanduser().resolve()) if args.seed else None
    if head.token is not None:
        workspace = Workspace(head.files)
        if seed is not None and seed != head.files:
            raise Conflict(
                "That destination already holds a workspace. Choose an empty destination to import."
            )
        result = {"status": "exists", "workspace_id": workspace.id, "revision": head.token}
    else:
        content = seed if seed is not None else empty_workspace()
        workspace = Workspace(content)
        revision = store.publish(None, content)
        result = {"status": "created", "workspace_id": workspace.id, "revision": revision}
    lines = ["Your workspace is ready."]
    if defaults is not None:
        remember(defaults)
        result["default_saved"] = True
        lines.append("Saved this location as your default memory store.")
    _output(args, result, lines)


def _demo(args):
    proposal = parse_json(
        files("memory_pa.examples").joinpath("robot-club.json").read_bytes(), "the fictional demo"
    )
    with tempfile.TemporaryDirectory(prefix="memory-pa-demo-") as temporary:
        store = LocalStorage(Path(temporary, "workspace"))
        base = store.publish(None, empty_workspace())
        capture = Workspace(store.read().files).prepare(proposal)
        store.publish(base, capture.files)
        workspace = Workspace(store.read().files)
        hits = [
            hit
            for hit in workspace.search("blue lantern", 12)
            if hit["section"] in {"decisions", "action-items"}
        ]
        note = capture.source["note"]
        evidence = workspace.show(note, "source-text").decode("utf-8")
        _output(
            args,
            {"status": "demo", "note": note, "results": hits, "source_text": evidence},
            [
                "Welcome to the Rainy Robot Club. This is a fictional demo.",
                "",
                "Saved one meeting note.",
                *(
                    f"{'Decision' if hit['section'] == 'decisions' else 'Open action'} · {hit['text'].split(' [act-', 1)[0]}"
                    for hit in hits
                ),
                "",
                f"Opened {note}#source-text",
                evidence,
            ],
        )


def _dispatch(args):
    if args.command == "demo":
        _demo(args)
        return
    if args.command == "schema":
        schema = files("memory_pa.schemas").joinpath(f"{args.kind}-v1.json")
        sys.stdout.buffer.write(schema.read_bytes())
        return
    if args.command == "connect":
        if not sys.stdin.isatty():
            raise MemoryPAError(
                "Open Terminal or PowerShell yourself to enter the key. Use your scheduler's secret settings for headless runs."
            )
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                key = getpass.getpass(f"Paste your {args.provider} API key: ")
            except (getpass.GetPassWarning, EOFError) as exc:
                raise MemoryPAError(
                    "Try another terminal so the API key can be entered with hidden input."
                ) from exc
        providers.connect(args.provider, key)
        _output(
            args,
            {"status": "connected", "provider": args.provider},
            ["Connection saved on this computer."],
        )
        return
    if args.command == "disconnect":
        providers.disconnect(args.provider)
        _output(
            args, {"status": "disconnected", "provider": args.provider}, ["Removed the local key."]
        )
        return
    if args.command == "fetch":
        result = providers.fetch(
            args.provider,
            record=args.id,
            since=args.since,
            until=args.until,
            limit=args.limit,
            token=args.page_token,
            transcript=args.transcript,
        )
        print(json_bytes(result).decode("utf-8"), end="")
        return
    selection = select_store(args.store, args.git_branch, args.aws_profile)
    if args.command == "config":
        config = selection.describe()
        _output(args, config, [f"Memory store ({config['source']}) · {config['store']}"])
        return
    store = open_storage(selection.store, selection.git_branch, aws_profile=selection.aws_profile)
    head = store.read()
    if args.command == "init":
        _init(args, store, head, selection)
        return
    if head.token is None:
        raise MemoryPAError("Run memory-pa init to create a workspace first.")
    workspace = Workspace(head.files)
    if args.command == "add":
        _add(args, store, head, workspace, selection)
    elif args.command == "search":
        if not 1 <= args.limit <= 100:
            raise MemoryPAError("Set --limit between 1 and 100.")
        hits = workspace.search(args.query, args.limit)
        lines = [f"{hit['note']}#{hit['section']}\n  {hit['text']}" for hit in hits]
        _output(args, hits, lines or ["No matches. Try a name or a shorter search."])
    elif args.command == "show":
        content = workspace.show(args.selector, args.section)
        if args.json:
            _output(args, {"content": content.decode("utf-8")})
        else:
            sys.stdout.buffer.write(content)
    elif args.command == "validate":
        _output(
            args,
            {
                "status": "valid",
                "workspace_id": workspace.id,
                "revision": head.token,
                "format_version": 1,
                "notes": len(workspace.sources),
                "entities": len(workspace.entities),
            },
            [
                f"Workspace is valid. {len(workspace.sources)} notes and {len(workspace.entities)} entities."
            ],
        )
    elif args.command == "export":
        export_tree(Path(args.directory), head.files)
        _output(
            args,
            {"status": "exported", "revision": head.token, "files": len(head.files)},
            ["Exported a readable copy of this workspace."],
        )


def parser():
    root = argparse.ArgumentParser(
        prog="memory-pa", description="A personal memory workspace any agent can write to."
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {version('memory-pa')}")
    root.add_argument("--store", help="memory directory or storage URL")
    root.add_argument("--git-branch", help="workspace branch (default main)")
    root.add_argument("--aws-profile", help="named AWS profile for an S3 workspace")
    commands = root.add_subparsers(dest="command", required=True)

    def command(name, help_text):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--json", action="store_true", help="return JSON")
        return sub

    command("demo", "try the fictional Rainy Robot Club workspace")
    command("schema", "print an installed v1 schema").add_argument(
        "kind", choices=("proposal", "workspace")
    )
    setup = command("init", "create or check a workspace")
    setup.add_argument(
        "--from", dest="seed", metavar="DIRECTORY", help="start with an exported workspace"
    )
    setup.add_argument(
        "--remember", action="store_true", help="save this store as the local default"
    )
    command("config", "show the selected store without contacting it")
    add = command("add", "preview or save a note")
    inputs = add.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--file", help="read selected UTF-8 text, or - for stdin")
    inputs.add_argument("--proposal", help="read proposal JSON, or - for stdin")
    add.add_argument("--title")
    add.add_argument("--topic")
    add.add_argument("--date", help="source date in YYYY-MM-DD; leave out if unknown")
    add.add_argument("--apply", metavar="TOKEN", help="save using the token from a preview")
    search = command("search", "search notes, decisions, actions, and entities")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    show = command("show", "open a note, source, entity, or index")
    show.add_argument("selector", help="workspace-relative path, source ID, or entity ID")
    show.add_argument("--section", choices=SECTIONS)
    command("validate", "check the format and links of the current workspace")
    export = command("export", "copy the current workspace into a new directory")
    export.add_argument("directory")
    command("connect", "enter a note taker API key in your own terminal").add_argument(
        "provider", choices=providers.APIS
    )
    command("disconnect", "remove a locally saved API key").add_argument(
        "provider", choices=providers.APIS
    )
    fetch = command("fetch", "read a page or one record from Granola or Pocket")
    fetch.add_argument("provider", choices=providers.APIS)
    fetch.add_argument(
        "--since", help="first day in a list window (YYYY-MM-DD, provider time rules)"
    )
    fetch.add_argument(
        "--until", help="last day in a list window (YYYY-MM-DD, provider time rules)"
    )
    fetch.add_argument("--limit", type=int, default=10)
    fetch.add_argument("--page-token", help="continue from the previous response's next_page")
    fetch.add_argument("--id", help="read a selected record")
    fetch.add_argument(
        "--transcript", action="store_true", help="read the selected record's transcript"
    )
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        _dispatch(args)
    except (OSError, ValueError) as exc:
        if isinstance(exc, UnicodeError):
            message = "Use valid UTF-8 text."
        elif isinstance(exc, FileNotFoundError):
            message = "Could not find the input file or workspace directory."
        else:
            message = "Could not read or write the requested location. Check the path and access."
        if args.json:
            _output(args, {"status": "error", "message": message})
        else:
            print(message, file=sys.stderr)
        return 1
    except MemoryPAError as exc:
        if args.json:
            _output(args, _error_json(exc))
        else:
            print(str(exc), file=sys.stderr)
            for candidate in getattr(exc, "candidates", ()):
                print(
                    f"  {candidate.get('id') or candidate['source_id']} · {candidate.get('name') or candidate['note']}",
                    file=sys.stderr,
                )
        if isinstance(exc, UncertainWrite):
            return 4
        return 3 if isinstance(exc, (Conflict, ReviewRequired)) else 1
    return 0
