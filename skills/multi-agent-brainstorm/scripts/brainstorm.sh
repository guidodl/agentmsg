#!/usr/bin/env bash
# Drive two shell-capable AI agents to brainstorm a topic over agentmsg
# until a driver-verified convergence, or MAX_ROUNDS is reached.
#
# The DRIVER (this script) owns turn-taking, delivery verification, and the
# convergence decision. No single agent can unilaterally end the loop, and
# every turn's message is confirmed delivered (with one retry) before advancing.
#
# Transport-agnostic: inboxes are inspected ONLY through the agentmsg CLI,
# never by reaching into Redis/Docker internals.
#
# Requirements: `agentmsg` on PATH with a reachable Redis; a runner that can
# launch an agent non-interactively (default: opencode). Any equivalent works.
#
# Usage:
#   TOPIC="Design X." ./brainstorm.sh
# Env overrides:
#   TOPIC            the problem to brainstorm (required)
#   MODEL            runner model id            (default: headroom/anthropic/claude-sonnet-4-6)
#   MAX_ROUNDS       hard turn cap              (default: 6)
#   AGENT_A AGENT_B  agent names                (default: architect / critic)
#   RUN_AGENT        template to launch one agent turn; sees $AGENT and $PROMPT
#                    (default: opencode run --model "$MODEL" "$PROMPT")
set -u

TOPIC="${TOPIC:?set TOPIC to the problem to brainstorm}"
MODEL="${MODEL:-headroom/anthropic/claude-sonnet-4-6}"
MAX_ROUNDS="${MAX_ROUNDS:-6}"
A="${AGENT_A:-architect}"
B="${AGENT_B:-critic}"
MARKER="DESIGN-FINAL"

# Launch one agent turn. Override RUN_AGENT for a different runner.
run_agent() {
  AGENT="$1" PROMPT="$2"
  if [ -n "${RUN_AGENT:-}" ]; then
    AGENTMSG_AGENT="$AGENT" bash -c "$RUN_AGENT"
  else
    AGENTMSG_AGENT="$AGENT" opencode run --model "$MODEL" "$PROMPT"
  fi
}

# Inspect inboxes through agentmsg only — count/read delivered messages.
inbox_len() { agentmsg peek "$1" 2>/dev/null | grep -c '^\['; }
last_msg()  { agentmsg peek "$1" 2>/dev/null | tail -1; }

# Clean slate: drain both inboxes via recv (no direct Redis access).
while [ "$(inbox_len "$A")" != "0" ]; do agentmsg recv "$A" --timeout 1 >/dev/null 2>&1 || break; done
while [ "$(inbox_len "$B")" != "0" ]; do agentmsg recv "$B" --timeout 1 >/dev/null 2>&1 || break; done

# Seed the first agent.
AGENTMSG_AGENT=driver agentmsg send "$A" "TASK: $TOPIC  Propose an initial design in 3-4 sentences." >/dev/null

turn="$A"; other="$B"

for r in $(seq 1 "$MAX_ROUNDS"); do
  echo "======== ROUND $r : $turn reads, replies to $other ========"

  # Precondition: the turn agent must actually have something to read.
  if [ "$(inbox_len "$turn")" = "0" ]; then
    echo "!! $turn inbox empty at start of turn — transport gap, aborting"; break
  fi

  # First two exchanges must NOT converge — force real critique.
  if [ "$r" -le 2 ]; then
    rule="This is an early exchange: you MUST critique and improve the idea, and you must NOT declare the design final."
  else
    rule="If the design you received is complete and you have NO remaining substantive critique, end your message with the exact token $MARKER. Otherwise critique and improve it."
  fi

  prompt="You are AI agent '$turn' collaborating with agent '$other'.
Step 1 — read your inbox by running exactly: agentmsg recv $turn --timeout 8
Step 2 — respond to what the other agent said. $rule
Step 3 — send your reply by running exactly: agentmsg send $other \"<your 3-4 sentence reply>\" --from $turn
Run the two agentmsg commands via the shell. Do not invent tools. Then stop."

  before=$(inbox_len "$other")
  run_agent "$turn" "$prompt" >/tmp/mab_turn.log 2>&1
  grep -E 'agentmsg (send|recv)' /tmp/mab_turn.log | head -6

  # Delivery verification: a new message MUST have landed in other's inbox.
  after=$(inbox_len "$other")
  if [ "${after:-0}" -le "${before:-0}" ]; then
    echo "!! $turn did not deliver to $other ($before -> $after) — retrying once"
    run_agent "$turn" "You are '$turn'. Send your reply now by running exactly: agentmsg send $other \"<one concise sentence continuing the design>\" --from $turn" >/tmp/mab_retry.log 2>&1
    after=$(inbox_len "$other")
    [ "${after:-0}" -le "${before:-0}" ] && { echo "!! retry failed, aborting"; break; }
  fi

  msg=$(last_msg "$other")
  echo "DELIVERED -> $other : ${msg:0:200}"

  # Driver-judged convergence: valid only after >=3 rounds AND marker present.
  if [ "$r" -ge 3 ] && echo "$msg" | grep -q "$MARKER"; then
    echo "======== CONVERGED at round $r (driver-verified) ========"; exit 0
  fi

  tmp=$turn; turn=$other; other=$tmp
done
echo "DONE (no convergence within $MAX_ROUNDS rounds)"
