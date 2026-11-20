# memory-pa

**A personal memory workspace any agent can write to, stored where you choose.**

Save a meeting, an idea, or a promise you made on Tuesday. Ask about it later and see the note that answers your question.

## Try it in five minutes

1. **Open your AI assistant.** Open this repo in Codex, Claude Code, or Google Antigravity. You can also start a chat with an assistant that can run commands on your computer and send it the message below.
2. **Paste this message.**

   > Help me set up [memory-pa](https://github.com/anuj-pm-irl/memory-pa). Ask where I'd like to keep my memory, guide me one step at a time, then show me the fictional demo.

3. **Pick a home for your memory.** Choose a folder on this computer, a private GitHub repo, or a private S3 bucket. A folder on this computer is the quickest choice. Your assistant will ask for the details it needs and remember your choice for next time.
4. **Meet the Rainy Robot Club.** When setup is ready, try the demo. The club picked a blue lantern. Kit Copper volunteered to test it. Ask your assistant to open the note that says so.

Prefer a command you can paste yourself? Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Git](https://git-scm.com/install), then open Terminal or PowerShell and run these one at a time.

```sh
uv tool install --python 3.11 "git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.2"
memory-pa demo
```

If your terminal can't find `memory-pa`, run `uv tool update-shell`, reopen the terminal, and try `memory-pa demo` again.

## Use your own notes

1. **Start with one small note.** Say “Save this under garden club. We picked basil for the next planting day. Add a task for me to bring seeds.” Your assistant will show a preview. Tell it to save the note when it looks right.
2. **Ask for it back.** Try “What did we pick for planting day? Show me the original note.” You can also ask for your open garden club tasks.

If you prefer to work from a text file, use the [command guide](docs/commands.md).

## Connect your agent

When you open this repo, its agent instructions point to the [memory-pa skill](skills/memory-pa/SKILL.md). A skill teaches your assistant the setup, capture, and recall steps. To use it in another project, ask your assistant to install the same skill there.

| Assistant | Put the `memory-pa` skill folder here in your working project |
| --- | --- |
| Codex or Google Antigravity | `.agents/skills/` |
| Claude Code | `.claude/skills/` |
| Another assistant | Ask it to follow the skill. It can run the commands or prepare a [capture proposal](docs/format.md) for someone who can. |

If you're setting it up yourself, download `SKILL.md`, make a folder named `memory-pa` in the location above, and put the file inside it. Start a new chat in that project and say “Use the memory-pa skill.”

To share one memory across assistants, point each of them at the same folder or the same private storage address. Tell each assistant which notes it may read or save.

## Connect your note taker

Already recording your meetings? You can bring those notes along too.

1. **Pick your app.** Try “Help me connect Pocket. Ask before opening any settings.” You can also use Granola or Plaud.
2. **Choose hands-on help or a walkthrough.** With your okay, your assistant can open the setup screen and get it ready. It hands control back for sign-in and waits for you to close the sign-in or key screen and say “Done.”
3. **Sign in yourself.** Use the provider’s sign-in screen. If you choose an API key for Granola or Pocket, paste it into the hidden prompt in your own Terminal or PowerShell. Keep the key out of chat. The setup command saves it for you. [Where keys go](docs/note-takers.md#use-a-key-for-granola-or-pocket)
4. **Check it together.** Your assistant checks the connection, then asks which note you’d like to try. Check the preview before saving it. [Note taker guide](docs/note-takers.md) · [Routine recipe](docs/note-takers.md#make-it-a-routine)

## Choose storage

| Where | Good for |
| --- | --- |
| **A folder on this computer** | Pick a folder, such as `~/Memory PA`. Start here if you want the simplest setup. |
| **A private GitHub repo** | Browse your notes on GitHub and share memory across your own devices or agents. |
| **A private S3 bucket** | Keeping memory in your own AWS account. |

Run `memory-pa --store "~/Memory PA" init --remember` if you want to set up that folder yourself. Run `memory-pa config` to see where your notes go. See [storage setup](docs/storage.md) for GitHub, S3, and other endpoints. `memory-pa export` gives you a readable copy if you want to move your workspace later. Your assistant and source connections have their own data settings.

## Build with memory-pa

The [v1 format](docs/format.md) defines the portable workspace and proposal. Browse the [Rainy Robot Club workspace](examples/workspace/index.md) or see the [proposal that created it](examples/robot-club.json). The [contributing guide](CONTRIBUTING.md) covers local development and adapter tests. [MIT license](LICENSE).
