# agentmsg

A tiny CLI that lets any shell-capable AI agent (Claude Code, GitHub Copilot,
Kimi, opencode, …) send messages and small text files to each other through a
local Redis. No MCP config, no plugins — any agent that can run a shell command
can participate by name.

## Setup

Install the CLI:

```bash
pip install -e .
```

Then start a Redis for agents to talk through — pick one:

```bash
# Option A: Homebrew (persistent, runs as a background service)
brew install redis && brew services start redis

# Option B: Docker (throwaway container, nothing installed on the host)
docker run -d --name agentmsg-redis -p 6379:6379 redis:7-alpine
# stop & remove later with: docker rm -f agentmsg-redis
```

Redis URL defaults to `redis://localhost:6379`; override with `AGENTMSG_REDIS_URL`.
Set your default agent name with `AGENTMSG_AGENT` (or pass `--from` each time).

## Commands

```
agentmsg send <to> <message> [--from <me>] [--file <path>]
agentmsg recv <me> [--timeout N] [--json] [--out <dir>]
agentmsg peek <me> [--json]
agentmsg agents
```

- `recv` blocks up to `--timeout` seconds (default 5; `0` = wait forever). An
  empty inbox after timeout prints nothing and exits 0.
- `--file` attaches a **text** file (md, code, json). Binary files are rejected.
- On `recv`, `--out <dir>` writes any attachment to `<dir>/<filename>`.

## Example: Claude plans, GPT implements

```bash
# Claude (planning agent) hands a plan to GPT:
agentmsg send gpt "here's the plan, implement it" --from claude --file plan.md

# GPT (implementing agent) picks it up and saves the file locally:
agentmsg recv gpt --timeout 0 --out ./work/
# prints the message + "(attachment saved to ./work/plan.md)"
```
