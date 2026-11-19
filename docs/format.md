# The memory-pa format

Format v1 is a directory of UTF-8 Markdown and JSON files. The same paths and bytes travel with the workspace when you move it. `memory-pa validate` checks the current tree against the [workspace schema](../schemas/workspace-v1.json), the note format, and the links between records.

When using an independent JSON Schema validator, load both v1 schemas by their `$id` so it can resolve references locally.

| Path | Contents |
| --- | --- |
| `workspace.json` | `format_version` and a stable `workspace_id` |
| `index.md` | A generated map of topics |
| `topics/<topic>/_summary.md` | Recent summaries, open actions, dated decisions, and links to the notes |
| `topics/<topic>/<title>-<date>.md` | A structured note followed by the selected original text |
| `sources/<source-id>.json` | Provenance, note path, source text hashes, decisions, and action history |
| `entities/<entity-id>.json` | One person, company, or project with source-linked mentions and facts |

A note uses `undated` when its date is unknown. Two different titles that produce the same filename use a source ID suffix to disambiguate. The capture time is separate from the event date. The selected text is stored as supplied after the `## Source text` heading. The source record's `text_sha256` verifies those exact UTF-8 bytes.

## Proposals

A [v1 proposal](../schemas/proposal-v1.json) requires `format_version`, `topic`, `title`, `source`, and `text`. You can add dates, a summary, decisions, actions, and entities. See the [fictional example](../examples/robot-club.json).

- Set `source.kind` to `note`, `file`, `meeting`, `recording`, `email`, `chat`, or `other`. If the source offers a stable ID, include `source.external` with `provider`, `account`, and `id`. Use a consistent account label for that provider. Include `source.url` when you have a link that people with access can open.
- Keep each decision and fact tied to the supplied text. Leave a date, speaker, or identity open when the source leaves it open. Add an explicit source-backed `basis` when linking a mention to an existing entity `id`. A matching name prompts for review. Set `distinct: true` after confirming the name belongs to a different entity.
- New actions get stable IDs and start `open` by default. To complete or update one, include its `id` and the new fields in a proposal with evidence from the same topic. Use `show` on the topic summary to find open action IDs. Earlier notes stay available in the action history.
- Provider records are matched by provider, account, and record ID. Other records are matched by source kind and an SHA-256 fingerprint of the NFC-normalized text with whitespace collapsed. A changed provider record or the same normalized title and date with a different body returns `review_required` with the original pointer.

The proposal size limit is 4 MiB, with up to 2 MiB of selected source text. Each workspace snapshot supports up to 10,000 files and 64 MiB in total. The only allowed snapshot files are the records, notes, and generated views described above. The CLI checks the format version before it can change a workspace.
