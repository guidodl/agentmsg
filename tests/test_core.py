import json
import fakeredis
from agentmsg import core

def make_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)

def test_inbox_key():
    assert core.inbox_key("claude") == "agentmsg:inbox:claude"

def test_touch_and_list_agents():
    c = make_client()
    core.touch_agent(c, "claude")
    core.touch_agent(c, "gpt")
    agents = core.list_agents(c)
    names = {a["agent"] for a in agents}
    assert names == {"claude", "gpt"}
    assert all("last_seen" in a for a in agents)
    raw = c.hget(core.REGISTRY_KEY, "claude")
    assert "last_seen" in json.loads(raw)

def test_send_pushes_envelope_and_touches_agents():
    c = make_client()
    env = core.send_message(c, "claude", "gpt", "hello")
    assert env["from"] == "claude"
    assert env["to"] == "gpt"
    assert env["body"] == "hello"
    assert "id" in env and "ts" in env
    assert "attachment" not in env

    raw = c.lindex(core.inbox_key("gpt"), 0)
    stored = json.loads(raw)
    assert stored["body"] == "hello"

    names = {a["agent"] for a in core.list_agents(c)}
    assert names == {"claude", "gpt"}

def test_send_with_attachment_includes_it():
    c = make_client()
    env = core.send_message(c, "claude", "gpt", "plan", {"filename": "plan.md", "content": "# Plan"})
    assert env["attachment"]["filename"] == "plan.md"
    assert env["attachment"]["content"] == "# Plan"
