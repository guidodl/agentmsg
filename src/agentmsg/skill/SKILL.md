---
name: agentmsg
description: Use when the user asks to message, send something to, or hear back from another AI agent by name (e.g. "send this to claude", "did copilot reply?", "check my agent inbox"). Sends/receives messages between agents over a local Redis bus via the agentmsg CLI.
---

# agentmsg — talking to other agents

Other AI agents share a local message bus via the `agentmsg` shell CLI. Your agent
name defaults to `$AGENTMSG_AGENT`, or `claude` if unset.

- **Send:** `agentmsg send <recipient> "<message>" --from <me>` — attach a text file with `--file <path>`.
- **Check inbox on demand:** `agentmsg recv <me> --timeout 5` — run this when the user asks whether another agent messaged you.
- **List known agents:** `agentmsg agents`.

Only send when the user asks you to message another agent. Do not poll in a loop
unless the user explicitly asks for a live back-and-forth.
