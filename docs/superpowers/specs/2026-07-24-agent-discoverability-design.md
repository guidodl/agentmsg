# agentmsg — agent discoverability (`init` + skill)

**Date:** 2026-07-24
**Status:** Design approved, ready for implementation planning

## Problem

agentmsg works mechanically, but a freshly launched harness (GitHub Copilot,
opencode, Kimi, …) has no idea the tool exists. When the user says "send a message
to claude," the agent doesn't know to run `agentmsg send claude ...`. This is a
discoverability / instruction problem, not a code problem: agents only do what
their instructions tell them, and nothing currently tells them agentmsg is the way
to reach other agents.

## Approach

Two tracks, because different harnesses learn conventions differently:

1. **`agentmsg init`** — writes an idempotent managed block into `AGENTS.md`, the
   emerging cross-harness instruction file. Any harness that auto-reads `AGENTS.md`
   then knows the tool exists, its own agent name, and how to send + receive on
   demand.
2. **A Claude Code skill** — Claude Code discovers capabilities through skills
   (and `CLAUDE.md`), not `AGENTS.md`. A bundled `agentmsg` skill teaches Claude
   the same convention. The skill is shipped in-repo (canonical copy) and can be
   installed globally by `init`.

Generic-only for `AGENTS.md`: we write a single file, not per-harness files
(`.github/copilot-instructions.md`, etc.). `AGENTS.md` is the cross-harness
standard and keeps scope minimal.

## Non-goals

- No per-harness instruction files. `AGENTS.md` only.
- No autonomous polling loop in the default instructions. The receive-reply loop
  from the README stays an opt-in snippet the user pastes when they explicitly
  want live ping-pong.
- `init` does not modify `CLAUDE.md` — Claude is covered by the skill.

## Command: `agentmsg init`

**Signature:** `agentmsg init [--name <me>] [--file <path>] [--skill] [--skills-dir <path>]`

| Flag | Meaning | Default |
|------|---------|---------|
| `--name` | Agent identity baked into the instruction block | `--name` → `$AGENTMSG_AGENT` → current directory basename |
| `--file` | Target instruction file | `./AGENTS.md` |
| `--skill` | Also install the Claude Code skill | off |
| `--skills-dir` | Where to install the skill | `$CLAUDE_SKILLS_DIR` → `~/.claude/skills/` |

### AGENTS.md managed block

Instructions are written between markers so the command is idempotent:

```
<!-- agentmsg:start -->
## Talking to other agents (agentmsg)

You are the **`{name}`** agent. Other AI agents share a local message bus via the
`agentmsg` CLI.

- To send: `agentmsg send <recipient> "<message>" --from {name}` (attach a text
  file with `--file <path>`).
- When the user asks whether another agent messaged you, or to check your inbox:
  `agentmsg recv {name} --timeout 5`.
- List known agents: `agentmsg agents`.

Only send when the user asks you to message another agent. Do not poll in a loop
unless explicitly told to.
<!-- agentmsg:end -->
```

`{name}` is substituted at write time.

### File-write rules (idempotent managed block)

- **File missing** → create it containing just the block.
- **File exists, no markers** → append the block, preceded by one blank line.
- **File exists, markers present** → replace only the text between (and including)
  the markers; leave all surrounding content byte-for-byte unchanged.

Output line: `agentmsg: wrote instructions to AGENTS.md (agent: copilot)`

### Skill install (`--skill`)

- Copies the canonical in-repo skill to `<skills-dir>/agentmsg/SKILL.md`.
- Idempotent: overwrites the managed copy on each run.
- Creates `<skills-dir>/agentmsg/` if absent.
- Output line: `agentmsg: installed skill to ~/.claude/skills/agentmsg/`

## Claude Code skill

Canonical copy bundled in the package at `src/agentmsg/skill/SKILL.md` (so it ships
on `pip install` and is copyable at runtime).

- **Name:** `agentmsg`
- **Description / trigger:** when the user asks to message / send to / hear from
  another agent by name, or to check for messages from other agents.
- **Body:** mirrors the `AGENTS.md` block, framed for Claude — send, on-demand
  `recv`, `agents`, and the same "don't poll unless asked" guardrail. Agent name
  defaults to `$AGENTMSG_AGENT` or `claude`.

Installation is dual:
- Canonical copy lives in-repo (travels with the project, documented in README).
- `init --skill` installs it into the global skills dir for use from any project.

## Testing

- `init` creates a fresh `AGENTS.md`; verify block + `{name}` substitution.
- Name-fallback chain: `--name`, then `$AGENTMSG_AGENT`, then directory basename.
- `--file` override targets a non-default path.
- Idempotency: append-once when markers absent; replace-in-place when markers
  present; surrounding content untouched.
- `--skill` copies `SKILL.md` into a temp `--skills-dir`; re-run overwrites cleanly.
- README updated with an `init` section (per project documentation rule).

## Files touched

- `src/agentmsg/cli.py` — add `init` subparser + handler.
- `src/agentmsg/init.py` (new) — block rendering, managed-block file write, skill copy.
- `src/agentmsg/skill/SKILL.md` (new) — canonical skill, bundled via packaging.
- `pyproject.toml` — ensure the skill file is included as package data.
- `tests/test_init.py` (new) — coverage above.
- `README.md` — document `init`.
