"""Capture the Stark archive and benchmark memory-pa against its gold queries."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from time import perf_counter_ns

from memory_pa.memory import Workspace
from memory_pa.storage.local import LocalStorage


HERE = Path(__file__).resolve().parent
NOTES = HERE / "notes"
CUTOFFS = (1, 5, 10)


def cli(store, command, *args, proposal=None):
    argv = [sys.executable, "-m", "memory_pa", "--store", str(store), command, "--json", *args]
    payload = json.dumps(proposal).encode("utf-8") if proposal is not None else None
    start = perf_counter_ns()
    process = subprocess.run(argv, input=payload, capture_output=True, timeout=30)
    elapsed_ms = (perf_counter_ns() - start) / 1_000_000
    if process.returncode:
        detail = (process.stdout or process.stderr).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"memory-pa {command} exited {process.returncode}: {detail}")
    return json.loads(process.stdout), elapsed_ms


def capture_archive(store, corpus):
    cli(store, "init")
    storage = LocalStorage(store)
    note_paths = {}
    action_ids = {}
    entity_ids = {}
    timings = []
    for entry in corpus:
        filename = entry["file"]
        note_file = NOTES / filename
        proposal = {
            **{key: value for key, value in entry.items() if key != "file"},
            "format_version": 1,
            "topic": note_file.parent.name,
            "text": note_file.read_bytes().decode("utf-8"),
            "actions": [],
            "entities": [],
        }
        for action in entry["actions"]:
            fields = {key: value for key, value in action.items() if key != "ref"}
            if action["ref"] in action_ids:
                fields["id"] = action_ids[action["ref"]]
            proposal["actions"].append(fields)
        for mention in entry["entities"]:
            fields = dict(mention)
            if "basis" in fields:
                fields["id"] = entity_ids[mention["kind"], mention["name"]]
            proposal["entities"].append(fields)

        preview, preview_ms = cli(store, "add", "--proposal", "-", proposal=proposal)
        if preview["status"] != "ready":
            raise RuntimeError(f"Unexpected capture preview for {filename}: {preview['status']}")
        saved, apply_ms = cli(
            store, "add", "--proposal", "-", "--apply", preview["apply_token"], proposal=proposal
        )
        if saved["status"] != "saved" or saved["note"] != preview["note"]:
            raise RuntimeError(f"Unexpected capture result for {filename}: {saved['status']}")
        timings.append(preview_ms + apply_ms)
        note_paths[filename] = saved["note"]
        source = json.loads(storage.read().files[f"sources/{saved['source_id']}.json"])
        for action, state in zip(entry["actions"], source["actions"], strict=True):
            action_ids[action["ref"]] = state["id"]
        for mention, entity_id in zip(entry["entities"], source["entities"], strict=True):
            entity_ids[mention["kind"], mention["name"]] = entity_id
    return note_paths, timings


def verify_evidence(store, cases, note_paths):
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Gold case IDs must be unique.")
    referenced = {name for case in cases for name in case["evidence"]}
    if referenced != note_paths.keys():
        raise ValueError("Gold evidence must cover every archive note and refer to saved notes.")
    texts = {}
    timings = []
    for filename, note_path in note_paths.items():
        result, elapsed = cli(store, "show", note_path, "--section", "source-text")
        text = result["content"]
        if text.encode("utf-8") != (NOTES / filename).read_bytes():
            raise ValueError(f"Source text changed during capture for {filename}.")
        texts[filename] = text
        timings.append(elapsed)
    for case in cases:
        for filename, quote in case["evidence"].items():
            if not quote.strip() or quote not in texts[filename]:
                raise ValueError(f"Missing evidence for {case['id']} in {filename}.")
    return timings


def timing(samples):
    ordered = sorted(samples)
    return {
        "samples": len(ordered),
        "p50": round(statistics.median(ordered), 3),
        "p95": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3),
    }


def run_search(store, workspace, cases, note_paths, cli_repeats, warm_repeats):
    limit = max(CUTOFFS)
    by_path = {path: filename for filename, path in note_paths.items()}
    reference = {case["id"]: workspace.search(case["query"], limit) for case in cases}
    cli_times = {case["id"]: [] for case in cases}
    warm_times = {case["id"]: [] for case in cases}
    order = list(cases)
    rng = random.Random(32)
    for _ in range(cli_repeats):
        rng.shuffle(order)
        for case in order:
            hits, elapsed = cli(store, "search", "--limit", str(limit), "--", case["query"])
            if hits != reference[case["id"]]:
                raise RuntimeError(f"CLI and workspace search results differ for {case['id']}.")
            cli_times[case["id"]].append(elapsed)
    for _ in range(warm_repeats):
        rng.shuffle(order)
        for case in order:
            start = perf_counter_ns()
            workspace.search(case["query"], limit)
            warm_times[case["id"]].append((perf_counter_ns() - start) / 1_000_000)

    rows = []
    for case in cases:
        case_id = case["id"]
        matches = []
        first_ranks = {}
        for rank, hit in enumerate(reference[case_id], 1):
            filename = by_path[hit["note"]]
            matches.append({"note": filename, "section": hit["section"]})
            first_ranks.setdefault(filename, rank)
        rows.append({
            "id": case_id,
            "group": case["group"],
            "query": case["query"],
            "gold_ranks": {name: first_ranks.get(name) for name in case["evidence"]},
            "matches": matches,
            "cli_search_ms": timing(cli_times[case_id]),
            "warm_search_ms": timing(warm_times[case_id]),
        })
    timings = {
        "cli_search": timing([sample for samples in cli_times.values() for sample in samples]),
        "warm_search": timing([sample for samples in warm_times.values() for sample in samples]),
    }
    return rows, timings


def score(rows):
    positives = [list(row["gold_ranks"].values()) for row in rows if row["gold_ranks"]]
    negatives = [row for row in rows if not row["gold_ranks"]]
    metrics = {"answerable": len(positives), "unanswerable": len(negatives)}
    if positives:
        for cutoff in CUTOFFS:
            counts = [sum(rank is not None and rank <= cutoff for rank in ranks) for ranks in positives]
            metrics[f"hits_at_{cutoff}"] = sum(count > 0 for count in counts)
            metrics[f"all_gold_at_{cutoff}"] = sum(
                count == len(ranks) for count, ranks in zip(counts, positives, strict=True)
            )
            metrics[f"mean_recall_at_{cutoff}"] = round(statistics.mean(
                count / len(ranks) for count, ranks in zip(counts, positives, strict=True)
            ), 4)
        first_ranks = [min((rank for rank in ranks if rank is not None), default=math.inf)
                       for ranks in positives]
        metrics[f"mrr_at_{max(CUTOFFS)}"] = round(statistics.mean(1 / rank for rank in first_ranks), 4)
    if negatives:
        metrics["empty_results"] = sum(not row["matches"] for row in negatives)
    return metrics


def dataset_hash(note_paths):
    checksum = hashlib.sha256()
    for path in [HERE / "corpus.json", HERE / "gold.json", *(NOTES / name for name in sorted(note_paths))]:
        checksum.update(path.relative_to(HERE).as_posix().encode("utf-8") + b"\0")
        checksum.update(path.read_bytes() + b"\0")
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-repeats", type=int, default=5, help="fresh CLI processes per query")
    parser.add_argument("--warm-repeats", type=int, default=40, help="loaded-workspace searches per query")
    parser.add_argument("--export", type=Path, metavar="NEW_DIRECTORY", help="export the built workspace")
    args = parser.parse_args()
    if args.cli_repeats < 1 or args.warm_repeats < 1:
        parser.error("repeat counts must be positive")

    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "gold.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="stark-archive-") as temporary:
        store = Path(temporary) / "workspace"
        note_paths, capture_times = capture_archive(store, corpus)
        stats, _ = cli(store, "validate")
        workspace = Workspace(LocalStorage(store).read().files)
        show_times = verify_evidence(store, cases, note_paths)
        rows, search_timings = run_search(
            store, workspace, cases, note_paths, args.cli_repeats, args.warm_repeats
        )
        if args.export:
            cli(store, "export", str(args.export.resolve()))

    groups = dict.fromkeys(case["group"] for case in cases)
    report = {
        "environment": {
            "memory_pa": version("memory-pa"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "jsonschema": version("jsonschema"),
            "storage": "local",
        },
        "dataset": {
            "sha256": dataset_hash(note_paths),
            "notes": stats["notes"],
            "entities": stats["entities"],
            "topics": len({source["topic"] for source in workspace.sources.values()}),
            "source_text_bytes": sum(len(text.encode("utf-8")) for text in workspace.text.values()),
            "snapshot_bytes": sum(len(data) for data in workspace.files.values()),
            "gold_cases": len(cases),
            "verified_evidence_quotes": sum(len(case["evidence"]) for case in cases),
        },
        "retrieval": {
            "overall": score(rows),
            "by_group": {group: score([row for row in rows if row["group"] == group]) for group in groups},
        },
        "latency_ms": {
            **search_timings,
            "cli_show_source": timing(show_times),
            "cli_capture_preview_and_apply": timing(capture_times),
        },
        "cases": rows,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
