# Connect your note taker

Start with one note. Once you can find it in memory-pa, you can hand the same job to a routine.

## Let your assistant help

1. **Tell it which app and account you want to use.** Try “Help me connect my Pocket work account to memory-pa.”
2. **Choose how much help you want.** Your assistant can talk you through each click. If it can use your screen, it can also open the official setup screen with your permission.
3. **Take over for sign-in.** Your assistant pauses while you sign in, create or enter a key, or review access. Close any screen that shows a password, key, or code, then say “Done” in chat. Your assistant can check the connection from there.

## Connect directly from your assistant

1. Open your assistant's **Connectors** or **MCP Servers** settings. Look for your note taker. If the settings let you add a custom MCP server, use its address from the table.
2. Sign into the note taker in the window that opens. Choose the account or workspace whose notes you want to use. Review the access it asks for and approve it yourself if you're happy with it.
3. Say “Done.” Your assistant can check the connection in its settings. When you're ready to try it, ask it to open a note you choose and show the save preview.

| App | Official MCP address | Setup guide |
| --- | --- | --- |
| Granola | `https://mcp.granola.ai/mcp` | [Granola MCP](https://docs.granola.ai/help-center/sharing/integrations/mcp) |
| Pocket | `https://public.heypocketai.com/mcp` | [Pocket MCP](https://docs.heypocketai.com/docs/mcp) |
| Plaud | `https://mcp.plaud.ai/mcp` | [Plaud MCP](https://support.plaud.ai/hc/en-us/articles/57751078986265-Plaud-MCP) |

Google Antigravity also supports custom remote MCP servers. Ask your assistant to walk you through its MCP settings. Your note taker's plan and workspace settings determine which notes and transcripts you can see. [Antigravity MCP setup](https://antigravity.google/docs/ide/mcp)

## Use a key for Granola or Pocket

Use this path if you prefer an API key. You'll paste it once into a hidden prompt in your own terminal. `memory-pa` saves it as plaintext under `~/.memory-pa/keys/` on that computer. macOS and Linux use owner-only file permissions. Windows uses the folder's account permissions. For a sign-in flow managed by your assistant's connector, use the [MCP setup above](#connect-directly-from-your-assistant).

1. **Create a key in your note taker.** Take control before generating it. In Granola, open **Settings → Connectors → API keys** and choose **Create new key**. API keys require Business or Enterprise. In Pocket, use **Settings → Developer → API Keys**. Pick the smallest read access that covers the notes you want.
2. **Open Terminal or PowerShell yourself.** Run just the line for your app.

   ```sh
   memory-pa connect granola
   memory-pa connect pocket
   ```

3. **Paste the key when the terminal asks.** Nothing appears as you type or paste. Press Enter. When you see “Connection saved on this computer,” close the page that shows the key and say “Done” in chat. That’s all your assistant needs.
4. **Let your assistant verify.** It runs `memory-pa connect granola --check --json` or `memory-pa connect pocket --check --json` where the key is set. The check makes a small read request and reports connection status. If the assistant runs on another computer, you can run the check in your own terminal and share the status.
5. **Choose one note to try.** Ask the assistant to open a note you pick, or to list a few titles so you can choose. The assistant opens only the selected item, then shows its save preview for your approval.

For a scheduled job, put `MEMORY_PA_GRANOLA_API_KEY` or `MEMORY_PA_POCKET_API_KEY` in the scheduler's secret settings. The job uses that environment key when present. Run `memory-pa disconnect APP` to remove the saved key from this computer. To revoke the key itself, use the provider's settings. [Granola API](https://docs.granola.ai/help-center/sharing/integrations/granola-api) · [Pocket API](https://docs.heypocketai.com/docs/api)

## Use Plaud from the terminal

Plaud provides MCP and a terminal app for reading personal recordings. To use the terminal path, follow the official install steps and run `plaud login`. Take control for the browser sign-in. Once you're done, your assistant can use `plaud files` or `plaud recent` with your okay, then `plaud summary ID` or `plaud transcript ID` for the item you select. [Plaud CLI](https://support.plaud.ai/hc/en-us/articles/57751026815257-Plaud-CLI) · [Plaud data access](https://support.plaud.ai/hc/en-us/articles/60726890231449-How-can-I-get-API-access-to-my-Plaud-data)

## Make it a routine

After you try one import, open the scheduling or routines feature of the assistant you use. Copy and edit this message. Pick the name of your note taker and the workspace where you want the notes to go.

> Each weekday at 6 p.m. in my time zone, check my connected Pocket account for new work recordings from the last two days. Look at up to ten per run. Use the source IDs so repeats are skipped. For each relevant recording, prepare a memory-pa preview with the decisions and open actions and a short excerpt that supports them. Show me the previews first. Report any items you couldn't read or need help identifying.

When the previews look right, you can tell your routine to apply them within that same scope. The routine needs access to your connected account, the `memory-pa` command, and the selected private workspace wherever it runs. Use the same provider account label on each run. A name match or changed source text can raise a review item.

For an API-backed routine, `fetch --since YYYY-MM-DD --until YYYY-MM-DD --limit 10` lists one page. Passing `--page-token` with the returned `next_page` continues the same window. Granola uses creation dates and Pocket uses UTC recording date filters. `next_page` can also appear for a Granola transcript. Collect the pages you need before treating a transcript as complete. If you stop at your run limit, report that more remain.

## Bring notes from another app

Use its official connector or export the note as text. Ask your assistant to make the same [capture proposal](format.md) with the app name, a stable record ID when available, and the excerpt you choose. Review one item before setting a routine for that source.
