import json
import os
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
