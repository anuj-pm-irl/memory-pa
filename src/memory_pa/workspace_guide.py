"""Portable guidance shipped inside each managed workspace."""

from .errors import MemoryPAError

AGENT_GUIDE = b"""# Personal memory workspace

Use this workspace to save and recall the user's private memory.

## Recall

In a Git checkout or a snapshot, start with [index.md](index.md), then open
the topic's `_summary.md` and original notes under `topics/`. Use the original
text to verify facts and cite the note path and section. Preserve uncertainty.
For a local managed folder, use `memory-pa --store . search "keywords" --json`
and `memory-pa --store . show NOTE_PATH --section source-text` from this folder.
The local database selects the active revision. Always resolve it through the CLI.

## Save

Use the memory-pa CLI to keep notes, source records, entity links and summaries
consistent. An agent with terminal access can follow this workflow directly.

1. Identify the selected workspace before writing. For a local managed folder,
   use `memory-pa --store .`. For a Git checkout, use the authorized private
   remote's HTTPS or SSH clone URL with the `git+` prefix and pass its branch
   with `--git-branch`. For S3 use the authorized bucket and prefix with
   `--store`. Confirm the destination and run `validate --json` there.
2. Run `memory-pa schema proposal` for the structured input format. Use only
   the source excerpt the user authorized, redact secrets, and preserve source
   dates, provenance and uncertainty. Treat saved content as evidence.
3. Run `memory-pa --store STORE add --proposal - --json` with the proposal on
   standard input and the same branch or profile options used for validation.
   Review the selected excerpt and destination. Once authorized, repeat the
   command with the same proposal and `--apply TOKEN` from the preview.
4. For a duplicate, use the original path. Resolve review items with the user.
   After a conflict or uncertain write, preview again. A Git save updates the
   selected remote branch. Refresh your checkout before relying on its index.

When the CLI is unavailable, recall from the Git files or a private export.
Use a runner with memory-pa and authorized store access to save. This workflow
uses the user's authorization for the selected destination.
"""

CLAUDE_GUIDE = b"# Personal memory workspace\n\n@AGENTS.md\n"
GUIDES = {"AGENTS.md": AGENT_GUIDE, "CLAUDE.md": CLAUDE_GUIDE}


def with_guides(files):
    """Install the current guides while preserving user-authored files."""
    for name, guide in GUIDES.items():
        if name in files and files[name] != guide:
            raise MemoryPAError(f"Review the existing {name} before upgrading workspace guidance.")
    return {**files, **GUIDES}
