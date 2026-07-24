import json
import os
import uuid
from datetime import datetime, timezone

import redis

DEFAULT_URL = "redis://localhost:6379"
REGISTRY_KEY = "agentmsg:agents"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_client(url: str | None = None) -> redis.Redis:
    resolved = url or os.environ.get("AGENTMSG_REDIS_URL") or DEFAULT_URL
    return redis.Redis.from_url(resolved, decode_responses=True)


def inbox_key(agent: str) -> str:
    return f"agentmsg:inbox:{agent}"


def touch_agent(client, agent: str) -> None:
    client.hset(REGISTRY_KEY, agent, json.dumps({"last_seen": _now()}))


def list_agents(client) -> list[dict]:
    entries = client.hgetall(REGISTRY_KEY)
    out = []
    for agent, raw in entries.items():
        data = json.loads(raw)
        out.append({"agent": agent, "last_seen": data.get("last_seen", "")})
    out.sort(key=lambda a: a["last_seen"], reverse=True)
    return out


def build_envelope(sender: str, to: str, body: str, attachment: dict | None = None) -> dict:
    env = {
        "id": str(uuid.uuid4()),
        "from": sender,
        "to": to,
        "body": body,
        "ts": _now(),
    }
    if attachment is not None:
        env["attachment"] = attachment
    return env


def send_message(client, sender: str, to: str, body: str, attachment: dict | None = None) -> dict:
    env = build_envelope(sender, to, body, attachment)
    client.lpush(inbox_key(to), json.dumps(env))
    touch_agent(client, sender)
    touch_agent(client, to)
    return env
