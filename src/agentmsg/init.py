START = "<!-- agentmsg:start -->"
END = "<!-- agentmsg:end -->"


def render_block(name: str) -> str:
    return f"""{START}
## Talking to other agents (agentmsg)

You are the **`{name}`** agent. Other AI agents share a local message bus via the `agentmsg` CLI.

- To send: `agentmsg send <recipient> "<message>" --from {name}` (attach a text file with `--file <path>`).
- When the user asks whether another agent messaged you, or to check your inbox: `agentmsg recv {name} --timeout 5`.
- List known agents: `agentmsg agents`.

Only send when the user asks you to message another agent. Do not poll in a loop unless explicitly told to.
{END}"""
