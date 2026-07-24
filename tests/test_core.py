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
