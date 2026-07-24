import json
import fakeredis
from agentmsg import cli

def run(argv, client):
    return cli.main(argv, _client=client)

def test_resolve_sender_precedence(monkeypatch):
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert cli.resolve_sender("explicit") == "explicit"
    monkeypatch.setenv("AGENTMSG_AGENT", "envagent")
    assert cli.resolve_sender(None) == "envagent"
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert cli.resolve_sender(None) == "anon"

def test_send_then_recv_roundtrip(capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    assert run(["send", "gpt", "hello", "--from", "claude"], c) == 0
    assert run(["recv", "gpt", "--timeout", "1"], c) == 0
    out = capsys.readouterr().out
    assert "hello" in out

def test_recv_empty_is_not_error(capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    assert run(["recv", "nobody", "--timeout", "1"], c) == 0

def test_agents_lists_participants(capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    run(["send", "gpt", "hi", "--from", "claude"], c)
    assert run(["agents"], c) == 0
    out = capsys.readouterr().out
    assert "claude" in out and "gpt" in out

def test_recv_json_outputs_envelope(capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    run(["send", "gpt", "hello", "--from", "claude"], c)
    run(["recv", "gpt", "--timeout", "1", "--json"], c)
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["body"] == "hello" and env["from"] == "claude"
