# agentmsg — universal cross-agent messaging CLI

**Date:** 2026-07-24
**Status:** Design approved, ready for implementation planning

## Purpose

Let any AI coding agent — Claude Code, GitHub Copilot, Kimi, opencode, or anything
else that can run a shell command — send messages (and small text files) to each
other. The design goal is **lightweight to use**: no MCP config, no per-harness
plugin, no shared filesystem. Any agent that can invoke a shell command can
participate by name.

Primary motivating workflow: use one agent for planning (e.g. Claude) and hand its
output to another for implementation (e.g. GPT) — including passing a `plan.md`
across.

## Non-goals

- Not an MCP server. (An earlier prototype, `agent-mailbox-mcp/`, took the MCP +
  shared-SQLite route; this project deliberately chooses a different, CLI-first
  architecture.)
- No binary file transfer — text files only (md, code, json).
- No live multi-agent "chat room" / broadcast in v1. Point-to-point inbox only.
  (Pub/sub broadcast is a possible later addition, explicitly out of scope now.)
- No auth / encryption — local, single-user, trusted environment.

## Architecture

- **Language / packaging:** Python + `redis-py`. Runnable via `uv run` and installable
  as a console-script entrypoint `agentmsg` (`pip install -e .`). Single small module.
- **Backend:** local Redis, default `redis://localhost:6379`, overridable via
  `AGENTMSG_REDIS_URL`.
- **Interaction model:** each agent has a durable inbox implemented as a Redis **list**.
  `send` does `LPUSH`; `recv` does `BLPOP` (blocking receive) with a timeout, so the
  receiver can wait for a message instead of polling. Messages persist until consumed.

### Redis keys

- `agentmsg:inbox:<agent>` — a **list**. Inbox for `<agent>`.
  - `send` → `LPUSH agentmsg:inbox:<to> <envelope-json>`
  - `recv` → `BLPOP agentmsg:inbox:<me> <timeout>`
  - `peek` → `LRANGE agentmsg:inbox:<me> 0 -1` (no consume)
- `agentmsg:agents` — a **hash**, `<agent>` → JSON `{"last_seen": "<iso8601>"}`.
  Every `send` and `recv` upserts both the acting agent(s) so `agents` can list who is
  around. No TTL in v1 (entries persist).

### Message envelope (JSON stored in the list)

```json
{
  "id": "<uuid4>",
  "from": "claude",
  "to": "gpt",
  "body": "here's the plan, implement it",
  "ts": "2026-07-24T14:40:00Z",
  "attachment": {
    "filename": "plan.md",
    "content": "<full utf-8 text of the file>"
  }
}
```

`attachment` is present only when `--file` was passed. Content is stored **inline**
(no separate blob store, no shared filesystem). Redis handles multi-KB string values
fine; a plan/markdown/code file is small.

## CLI surface

```
agentmsg send <to> <message> [--from <me>] [--file <path>]
agentmsg recv <me> [--timeout N] [--json] [--out <dir>]
agentmsg peek <me> [--json]
agentmsg agents [--json]
```

**Command behavior:**

- `send <to> <message>`
  - Builds an envelope, `LPUSH`es it to `<to>`'s inbox, upserts both `<from>` and `<to>`
    in the agents hash.
  - `--from <me>` sets the sender identity. If omitted, resolve from `AGENTMSG_AGENT`
    env var; if that is unset, default to a stable fallback (e.g. `"anon"` or the
    system username — see Open-resolved detail below). Sender is metadata only.
  - `--file <path>` reads the file as UTF-8 and embeds it as `attachment`. Missing/
    unreadable path → error, exit non-zero. Non-UTF-8 (binary) content → refuse with a
    "text-only" message, exit non-zero.

- `recv <me>`
  - `BLPOP agentmsg:inbox:<me>` with `--timeout N` seconds. `N=0` means block forever;
    default is a finite timeout (e.g. `5`) so it never hangs unexpectedly.
  - Empty after timeout is **not an error**: print nothing (or `{}` with `--json`),
    exit 0, so scripts can loop cleanly.
  - On a message: print `body`. If an attachment exists, note it and print its content
    to stdout so the receiving agent sees it inline.
  - `--out <dir>`: additionally write the attachment to `<dir>/<filename>` and print the
    saved path.
  - `--json`: print the full envelope as JSON instead of the human-readable form.
  - Upserts `<me>` in the agents hash.

- `peek <me>` — `LRANGE` the inbox without consuming; print bodies (or JSON with `--json`).

- `agents` — read the agents hash, print each agent + `last_seen`, sorted by most recent.

## Error handling

Validate only at real boundaries; trust internal state otherwise.

- **Redis unreachable** → single clear line, e.g.
  `agentmsg: cannot reach Redis at <url> — is it running? try 'brew services start redis'`,
  exit non-zero. This is the main failure agents will hit.
- **`--file` path missing / unreadable** → clear error, exit non-zero.
- **`--file` non-UTF-8 (binary)** → refuse, "text files only", exit non-zero.
- **`recv` timeout, empty inbox** → not an error; empty output, exit 0.

## Testing

- Use **`fakeredis`** so the suite needs zero running infrastructure. (Chosen over a live
  Redis for zero-setup; the code path is identical `redis-py` API.)
- Cover:
  - `send` → `recv` round-trip (body only).
  - Blocking `recv` wakes when a `send` arrives during the wait.
  - `recv` timeout with empty inbox returns empty, exit 0.
  - File attachment round-trips: inline content present; `--out` writes the file to disk
    with correct name and content.
  - Binary/non-UTF-8 `--file` is rejected.
  - `agents` lists both senders and receivers with last-seen.

## Documentation

- Project `README.md`: usage, the "Claude plans / GPT implements" example with `--file`,
  Redis setup (`brew install redis` / `brew services start redis`), and the
  `AGENTMSG_REDIS_URL` / `AGENTMSG_AGENT` env vars.

## Open detail to resolve during planning

- Exact default sender identity when neither `--from` nor `AGENTMSG_AGENT` is set
  (`"anon"` vs. system username). Minor; pick one in the plan.
