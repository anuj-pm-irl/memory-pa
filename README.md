# memory-pa

**A personal memory workspace any agent can write to, stored where you choose.**

Save a meeting, an idea, or a promise you made on Tuesday. Ask about it later and see the note that answers your question.

## Try it in five minutes

1. **Open your AI assistant.** Start a chat in Codex, Claude Code, or Google Antigravity where it can run commands on your computer.
2. **Paste this message.**

   > Help me try [memory-pa](https://github.com/anuj-pm-irl/memory-pa). Follow its install instructions and run `memory-pa demo`. Use the fictional notes for this first run. Tell me what the club decided, who has the next action, and which note you used.

3. **Meet the Rainy Robot Club.** The club picked a blue lantern. Kit Copper volunteered to test it. Your assistant should be able to open the note that says so.

Prefer a command you can paste yourself? Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Git](https://git-scm.com/install), then open Terminal or PowerShell and run these one at a time.

```sh
uv tool install --python 3.11 "git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.0"
memory-pa demo
```

If your terminal can't find `memory-pa`, run `uv tool update-shell`, reopen the terminal, and try `memory-pa demo` again.

## Use your own notes

1. **Give your memory a home.** Say “Set up memory-pa on this computer.” Your assistant can run `memory-pa init`. This creates your own workspace in your home folder.
2. **Start with one small note.** Say “Save this under garden club. We picked basil for the next planting day. Remind me to bring seeds.” Your assistant should show you what it plans to save. Tell it to save the note when the preview looks right. An action item will appear in the memory for you to look up later.
3. **Ask for it back.** Try “What did we pick for planting day? Show me the original note.” You can also ask for your open garden club actions.

If you prefer to work from a text file, use the [command guide](docs/commands.md).

## Connect your agent

Ask your assistant to install the [memory-pa skill](skills/memory-pa/SKILL.md). A skill is a short set of instructions that teaches your assistant how to save notes and look up evidence. Use the same file for each assistant you want to use.

| Assistant | Put the `memory-pa` skill folder here in your working project |
| --- | --- |
| Codex or Google Antigravity | `.agents/skills/` |
| Claude Code | `.claude/skills/` |
| Another assistant | Ask it to follow the skill. It can run the commands or prepare a [capture proposal](docs/format.md) for someone who can. |

If you're setting it up yourself, download `SKILL.md`, make a folder named `memory-pa` in the location above, and put the file inside it. Start a new chat in that project and say “Use the memory-pa skill.”

To share one memory across assistants, point each of them at the same folder or the same private storage address. Tell each assistant which notes it may read or save.

## Connect your note taker

Already recording your meetings? You can bring those notes along too.

1. Tell your assistant which app you use. Try “I use Pocket. Help me connect it and look up one note I pick.” The [note taker guide](docs/note-takers.md) covers Pocket, Granola, and Plaud.
2. Sign in through the connection screen if your assistant offers one. If you need an API key, the guide shows where to create it and where to paste it on your computer.
3. Pick one note and check the preview. When that works, use the [routine recipe](docs/note-takers.md#make-it-a-routine) to ask your assistant to pick up new notes on a schedule.

## Choose storage

| Where | Good for |
| --- | --- |
| **This computer** | A quick start. `memory-pa init` uses `~/.memory-pa/workspaces/default`. |
| **A private Git repository** | Browsing Markdown and sharing memory across your own devices or agents. |
| **A private S3 bucket** | Keeping memory in your own AWS account. |

See [storage setup](docs/storage.md) for Git, S3, and other endpoints. `memory-pa export` gives you a readable copy of your workspace so you can move it. The CLI sends data to the storage you select. Your assistant and source connectors have their own data settings.

## Build with memory-pa

The [v1 format](docs/format.md) defines the portable workspace and proposal. Browse the [Rainy Robot Club workspace](examples/workspace/index.md) or see the [proposal that created it](examples/robot-club.json). The [contributing guide](CONTRIBUTING.md) covers local development and adapter tests. [MIT license](LICENSE).
