# Commands

Use `memory-pa --help` and `memory-pa COMMAND --help` for the full options.

## Explore the Avengers archive

Run `memory-pa demo` to load all 18 fictional notes and see the evidence behind Happy Hogan’s menu-card task. The demo uses its bundled workspace. [Browse all six topics](../examples/workspace/index.md)

## Update memory-pa

1. Run `memory-pa --version`. Look for a newer published release and read its notes. [Latest memory-pa release](https://github.com/anuj-pm-irl/memory-pa/releases/latest)
2. On the machine or runner that uses your notes, run `memory-pa config --json` and `memory-pa validate --json` with the same settings and flags you use for normal commands. Keep the store settings and `workspace_id` for the check after updating. On v0.1.0, use your existing store settings and `validate`.
3. If the release notes ask you to convert your saved notes, read those instructions first. Make a backup with the working version using `memory-pa export NEW_PRIVATE_FOLDER`. If you’re guiding someone, explain what will change and get their approval before the backup and conversion.
4. Install the chosen release using the same installer and environment. For the `uv` quickstart, run `uv tool install` again with the new tag and the Python version the release requires. Keep the `s3` extra if you use S3 and carry over any extra adapter packages you installed. The examples below use `v0.1.3` and Python 3.11. [How uv updates tagged installs](https://docs.astral.sh/uv/concepts/tools/#upgrading-tools)

   For a folder or private GitHub, replace `v0.1.3` with the chosen tag and run this command.

   ```sh
   uv tool install --python 3.11 "git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.3"
   ```

   For S3, use the release tag in this command.

   ```sh
   uv tool install --python 3.11 "memory-pa[s3] @ git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.3"
   ```

5. Run `memory-pa --version`, `memory-pa config --json`, and `memory-pa validate --json` again. Check that the installed version matches the release and the store settings and workspace ID match your earlier check. If you copied the skill into your project, update that copy from `skills/memory-pa/SKILL.md` at the same release tag. Use it in your next chat.

If a routine update fails verification, install the previous tag with the same command and check the workspace again. For a release that changed how notes are stored, follow its recovery instructions.

## Save a note from a file

1. Run `memory-pa --store "~/Memory PA" init --remember` once to use that folder. Run `memory-pa config` any time to check where your notes go. See [storage setup](storage.md) for private GitHub and S3.
2. Put some text you want to save in `my-note.txt`. To follow the Avengers example, use the [original breakfast note](../benchmarks/stark-archive/notes/field-kitchen/breakfast-in-a-blackout.md). Run the command below to preview the note. Use a short topic with lowercase letters and hyphens. Add `--date YYYY-MM-DD` when you know the date the note is about.

   ```sh
   memory-pa add --file my-note.txt --title "Breakfast in a blackout" --topic field-kitchen --date 2032-06-07
   ```

3. Check the note and the paths shown in the preview. Copy the `--apply` option and its token from the output, then add them to the same command. The token ties the save to the same input and workspace revision.
4. Search for a word you remember and open a result.

   ```sh
   memory-pa search "menu cards"
   memory-pa show topics/field-kitchen/breakfast-in-a-blackout-2032-06-07.md --section source-text
   memory-pa show topics/field-kitchen/_summary.md
   ```

Use `--file -` to read pasted text from standard input. Use `--proposal path.json` or `--proposal -` for a structured note with decisions, actions, and entities. Pass the same input to both the preview and the save.

## Work with an agent or script

Use `memory-pa add --proposal - --json` for a preview, then repeat with `--apply APPLY_TOKEN`. A `ready` response contains the token, the note path, and the paths that will change. A `saved` or `duplicate` response gives the note path and source ID. Search returns records with `note`, `section`, `source_id`, `date`, `title`, and `text`.

`memory-pa show` accepts a workspace-relative file, note path, source ID, or entity ID. Use `--section` for a portion of a note or `--json` for a JSON wrapper. `memory-pa validate` checks the current workspace. `memory-pa export NEW_DIRECTORY` copies it as Markdown and JSON.

Run `memory-pa schema proposal` to read the exact installed proposal format. `memory-pa schema workspace` prints the workspace schema.

Use `memory-pa connect pocket --check --json` or `memory-pa connect granola --check --json` to check API access after entering a key or setting a job secret. It returns the provider and `verified` on success. To enter a new key, run `memory-pa connect pocket` or `memory-pa connect granola` in your own terminal. [Connection setup](note-takers.md)

Exit code `0` means the command succeeded, including an already-saved note. `1` means invalid input, access trouble, or another operation error. `2` means a command syntax error. `3` means a stale revision or a note or identity that needs review. `4` means the adapter could not confirm the write. Run another preview after a `3` or a `4`. It will show an existing note if the write already landed.
