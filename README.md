# memory-pa

Save a note with your AI assistant. Later, ask a question about it and see the note behind the answer. You choose where your notes live.

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="docs/media/stark-archive-comic.png">
  <img src="docs/media/save-ask-answer.gif" width="780" alt="Three-panel Stark Archive comic. Happy Hogan says he’ll bring the sample menu cards. Tony Stark asks who’s bringing them. Memory-pa answers Happy Hogan and opens the June 7 note.">
</picture>

[Read the source behind the comic](examples/workspace/topics/field-kitchen/breakfast-in-a-blackout-2032-06-07.md#source-text)

The **Stark Archive** is the complete fictional Avengers demo, with 18 notes across six topics. [Browse the workspace](examples/workspace/index.md) · [Read the source notes and benchmark questions](benchmarks/stark-archive/README.md)

## Start in chat

Open Codex, Claude Code, or Google Antigravity. **Copy this one message into chat.**

```text
Set up memory-pa with me. Start by asking where I want my notes to live.
Guide me one step at a time and do the setup I approve.
Follow the setup skill in https://github.com/anuj-pm-irl/memory-pa
```

1. **Choose where to keep your notes.** Pick a folder on your computer, private GitHub, or private S3. A folder on your computer is the easiest place to start.
2. **Let your assistant set it up.** Say yes to the steps you want it to do.
3. **Explore the Avengers archive.** Say **“Run the demo with me.”** It loads the full archive and answers **“Who will bring sample menu cards to the handoff dry run?”**

If you need to sign in, your assistant will pause so you can do it yourself. If you need an API key, it will guide you to a hidden prompt in your own terminal. Close the screen showing the key and say **“Done.”**

## Save your first note

Say **“Remember this”** and tell your assistant what to save. It will show you what it plans to keep. Say **“Yes, save it”** if it looks right. When you ask about it later, you can say **“Show me the note you used.”**

Already use a note taker? Say **“Help me connect Pocket and try one note.”** You can do the same with Granola or Plaud. [Note taker setup](docs/note-takers.md) · [Set up a routine](docs/note-takers.md#make-it-a-routine)

## How the memory map grows

memory-pa keeps your original note and links what you want to remember back to it.

<img src="docs/media/stark-archive-memory-map.png" width="780" alt="Stark Archive detective board. Red thread connects Breakfast in a blackout to the Red Hook delivery decision, Happy Hogan’s open task, and Sam Wilson’s call. Two notes from Tower Access and Roof Garden connect to the same James Rhodes sticker.">

Follow the red thread from the field kitchen note to Happy Hogan’s open task, or from two different topics to James Rhodes. The board shows selected connections from the 18-note archive. [Field kitchen note](examples/workspace/topics/field-kitchen/breakfast-in-a-blackout-2032-06-07.md) · [Browse all six topics](examples/workspace/index.md)

[How memory-pa builds the map](docs/format.md#how-the-memory-map-is-built)

## Update in chat

When you’re ready to check for a new version, paste this into your assistant’s chat.

```text
Check for a memory-pa update and tell me what’s new. Ask before installing it.
After the update, check that you can still open my existing notes.
Follow https://github.com/anuj-pm-irl/memory-pa/blob/main/docs/commands.md#update-memory-pa
```

Your assistant can update the tool and the skill you copied into your project. If a release changes how notes are stored, it will explain the change and ask about a private backup first. [Update in Terminal](docs/commands.md#update-memory-pa)

<details>
<summary>Set up in Terminal</summary>

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Git](https://git-scm.com/install), then run these in Terminal or PowerShell.

```sh
uv tool install --python 3.11 "git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.3"
memory-pa demo
memory-pa --store "~/Memory PA" init --remember
```

Replace `~/Memory PA` with the folder you want. The tagged release above includes the earlier demo. To run the Avengers demo from this checkout, follow the [development setup](CONTRIBUTING.md). If your terminal can’t find `memory-pa`, run `uv tool update-shell`, reopen the terminal, and try again. [Command guide](docs/commands.md) · [Private GitHub and S3 setup](docs/storage.md)

</details>

<details>
<summary>Use the skill in another project</summary>

Ask your assistant to install the [memory-pa skill](skills/memory-pa/SKILL.md) in that project. To do it yourself, save the file as `.agents/skills/memory-pa/SKILL.md` for Codex or Antigravity, or `.claude/skills/memory-pa/SKILL.md` for Claude Code. Start a new chat and say “Use the memory-pa skill.”

Share a memory across assistants by pointing them at the same folder or private storage address. [Storage guide](docs/storage.md)

</details>

[Contributing](CONTRIBUTING.md) · [MIT license](LICENSE)
