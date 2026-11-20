# Commands

Use `memory-pa --help` and `memory-pa COMMAND --help` for the full options.

## Save a note from a file

1. Run `memory-pa --store "~/Memory PA" init --remember` once to use that folder. Run `memory-pa config` any time to check where your notes go. See [storage setup](storage.md) for private GitHub and S3.
2. Put some text you want to save in `my-note.txt`. Run the command below to preview the note. Use a short topic with lowercase letters and hyphens. Add `--date YYYY-MM-DD` when you know the date the note is about.

   ```sh
   memory-pa add --file my-note.txt --title "Planting day" --topic garden-club
   ```

3. Check the note and the paths shown in the preview. Copy the `--apply` option and its token from the output, then add them to the same command. The token ties the save to the same input and workspace revision.
4. Search for a word you remember and open a result.

   ```sh
   memory-pa search "basil"
   memory-pa show topics/garden-club/planting-day-undated.md --section source-text
   memory-pa show topics/garden-club/_summary.md
   ```

Use `--file -` to read pasted text from standard input. Use `--proposal path.json` or `--proposal -` for a structured note with decisions, actions, and entities. Pass the same input to both the preview and the save.

## Work with an agent or script

Use `memory-pa add --proposal - --json` for a preview, then repeat with `--apply APPLY_TOKEN`. A `ready` response contains the token, the note path, and the paths that will change. A `saved` or `duplicate` response gives the note path and source ID. Search returns records with `note`, `section`, `source_id`, `date`, `title`, and `text`.

`memory-pa show` accepts a workspace-relative file, note path, source ID, or entity ID. Use `--section` for a portion of a note or `--json` for a JSON wrapper. `memory-pa validate` checks the current workspace. `memory-pa export NEW_DIRECTORY` copies it as Markdown and JSON.

Run `memory-pa schema proposal` to read the exact installed proposal format. `memory-pa schema workspace` prints the workspace schema.

Exit code `0` means the command succeeded, including an already-saved note. `1` means invalid input, access trouble, or another operation error. `2` means a command syntax error. `3` means a stale revision or a note or identity that needs review. `4` means the adapter could not confirm the write. Run another preview after a `3` or a `4`. It will show an existing note if the write already landed.
