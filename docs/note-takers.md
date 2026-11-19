# Connect your note taker

Start with one note. Once you can find it in memory-pa, you can hand the same job to a routine.

## Connect directly from your assistant

1. Open your assistant's **Connectors** or **MCP Servers** settings. Look for your note taker. If the settings let you add a custom MCP server, you can paste its address from the table.
2. Sign into the note taker in the window that opens. Choose the account or workspace whose notes you want to use.
3. Tell your assistant “Show me a few recent note titles. I'll pick one for memory-pa.” Pick a title and check the save preview.

| App | Official MCP address | Setup guide |
| --- | --- | --- |
| Granola | `https://mcp.granola.ai/mcp` | [Granola MCP](https://docs.granola.ai/help-center/sharing/integrations/mcp) |
| Pocket | `https://public.heypocketai.com/mcp` | [Pocket MCP](https://docs.heypocketai.com/docs/mcp) |
| Plaud | `https://mcp.plaud.ai/mcp` | [Plaud MCP](https://support.plaud.ai/hc/en-us/articles/57751078986265-Plaud-MCP) |

Google Antigravity also supports custom remote MCP servers. Ask your assistant to walk you through its MCP settings. Your note taker's plan and workspace settings determine which notes and transcripts you can see. [Antigravity MCP setup](https://antigravity.google/docs/ide/mcp)

## Use a key for Granola or Pocket

Use this path if your assistant can run `memory-pa` commands and you prefer to connect with an API key.

1. **Create a key in your note taker.** In Granola, open **Settings → Connectors → API keys** and choose **Create new key**. API keys require Business or Enterprise. In Pocket, use **Settings → Developer → API Keys**. Pick the smallest read access that covers the notes you want.
2. **Open Terminal or PowerShell yourself.** Run `memory-pa connect granola` or `memory-pa connect pocket`. Paste the key at the prompt and press Enter. The key stays hidden as you type and is stored in a local credential file under `~/.memory-pa/keys/`. Paste keys here, away from chats, notes, and project files.
3. **Ask for a sample.** Say “Use memory-pa to list three recent Pocket recordings. I'll choose which one to save.” Your assistant can run one of these commands.

   ```sh
   memory-pa fetch pocket --limit 3
   memory-pa fetch granola --limit 3
   ```

4. **Choose what to keep.** The assistant can read your selected item with `memory-pa fetch pocket --id RECORD_ID` or `memory-pa fetch granola --id NOTE_ID`. Add `--transcript` when you want the transcript and your account allows it. The assistant turns the selected text into a proposal for you to review.

For a scheduled job running on another computer, set `MEMORY_PA_GRANOLA_API_KEY` or `MEMORY_PA_POCKET_API_KEY` as a secret in the job's environment. Use `memory-pa disconnect APP` to remove the saved key from this computer. The provider's settings manage the key itself. [Granola API](https://docs.granola.ai/help-center/sharing/integrations/granola-api) · [Pocket API](https://docs.heypocketai.com/docs/api)

## Use Plaud from the terminal

Plaud provides MCP and a terminal app for reading personal recordings. To use the terminal path, follow the official install steps and sign in with `plaud login`. Your assistant can use `plaud files` or `plaud recent`, then `plaud summary ID` or `plaud transcript ID` for the item you select. Ask it to import the result as it would a note from MCP. [Plaud CLI](https://support.plaud.ai/hc/en-us/articles/57751026815257-Plaud-CLI) · [Plaud data access](https://support.plaud.ai/hc/en-us/articles/60726890231449-How-can-I-get-API-access-to-my-Plaud-data)

## Make it a routine

After you try one import, open the scheduling or routines feature of the assistant you use. Copy and edit this message. Pick the name of your note taker and the workspace where you want the notes to go.

> Each weekday at 6 p.m. in my time zone, check my connected Pocket account for new work recordings from the last two days. Look at up to ten per run. Use the source IDs so repeats are skipped. For each relevant recording, prepare a memory-pa preview with the decisions and open actions and a short excerpt that supports them. Show me the previews first. Report any items you couldn't read or need help identifying.

When the previews look right, you can tell your routine to apply them within that same scope. The routine needs access to your connected account, the `memory-pa` command, and the selected private workspace wherever it runs. Use the same provider account label on each run. A name match or changed source text can raise a review item.

For an API-backed routine, `fetch --since YYYY-MM-DD --until YYYY-MM-DD --limit 10` lists one page. Passing `--page-token` with the returned `next_page` continues the same window. Granola uses creation dates and Pocket uses UTC recording date filters. `next_page` can also appear for a Granola transcript. Collect the pages you need before treating a transcript as complete. If you stop at your run limit, report that more remain.

## Bring notes from another app

Use its official connector or export the note as text. Ask your assistant to make the same [capture proposal](format.md) with the app name, a stable record ID when available, and the excerpt you choose. Review one item before setting a routine for that source.
