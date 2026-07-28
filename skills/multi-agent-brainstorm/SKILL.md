---
name: multi-agent-brainstorm
description: Use when two or more independent AI agents should debate a design or problem back-and-forth over a shared message bus until they agree on a solution.
allowed-tools: Read, Write, Edit, Bash
license: MIT
metadata:
  author: Guido Di Lauro
  version: "1.0"
---

# Multi-Agent Brainstorm

## Overview

Let shell-capable AI agents brainstorm a problem by exchanging messages over a CLI message bus (e.g. `agentmsg`) — no MCP or plugins — until they converge on a solution.

**Core principle: the DRIVER owns control flow, not the agents.** A neutral driver loop decides turn-taking, verifies each message was delivered, and judges convergence; agents only think and send. This stops the three failure modes below.

## When to Use

- Diverse independent agents should critique and improve each other's ideas (architect vs. critic, proposer vs. red-team).
- You want a design debated to consensus, not one model's single-shot answer.
- Agents share only a message bus — no shared memory or filesystem.

**When NOT to use:** a single well-prompted agent suffices, or the task needs deterministic control flow.

## The Three Failure Modes (and the guards)

Naive "agent A sends, agent B replies" loops fail these ways — each guard is in `scripts/brainstorm.sh`:

| Failure | What it looks like | Guard |
|---|---|---|
| **Premature convergence** | An agent declares "done" on turn 1 before the other has spoken. | Convergence invalid before round 3 AND requires an explicit marker token; the driver decides, not the agent. |
| **Dropped-message cascade** | One `send` silently fails → next agent's inbox is empty → it hallucinates a reply or invents a fake "the bus is broken" story. | After every turn the driver confirms a new message landed in the peer's inbox; retries once, else aborts. |
| **Wrong-transport verification** | Driver checks inbox depth via the backing store (Redis/Docker) and reads the wrong instance → false "empty" aborts. | Inspect inboxes ONLY through the bus's own CLI (`peek`/`recv`), never its backing store. |

## Model Discipline

Drive turns with a **capable instruction-following model**. Weak models can't reliably run the multi-step `recv → think → send` protocol every turn — a single missed step triggers the dropped-message cascade above (a weak model tested here hallucinated a fake debugging exchange instead of following the protocol).

## Quick Start

```bash
TOPIC="Design a rate limiter for an API gateway, fair across tenants." \
  ./scripts/brainstorm.sh
```

Override via env: `MODEL`, `MAX_ROUNDS`, `AGENT_A`/`AGENT_B`, `RUN_ID` (a suffix isolating agent inboxes so concurrent runs don't collide — defaults to the script's PID), or `RUN_AGENT` (a launch template for a non-default runner — it receives `$AGENT` and `$PROMPT`).

## How the Loop Works

1. **Drain + seed** — clear both inboxes through the CLI, send the topic to agent A.
2. **Each round** — prompt the agent to `recv`, critique/improve, then `send` to the peer. Early rounds forbid convergence.
3. **Verify delivery** — confirm the peer's inbox grew; retry once, else abort.
4. **Judge convergence** — driver checks for the marker token, only after enough rounds.
5. **Swap** and repeat until converged or `MAX_ROUNDS`.

## Adapting

Transport- and harness-agnostic: swap `agentmsg` for any send/recv/peek CLI, and set `RUN_AGENT` to launch any agent non-interactively.
