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

def test_send_file_roundtrip_inline(tmp_path, capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\nstep 1", encoding="utf-8")
    run(["send", "gpt", "do this", "--from", "claude", "--file", str(plan)], c)
    run(["recv", "gpt", "--timeout", "1"], c)
    out = capsys.readouterr().out
    assert "plan.md" in out and "# Plan" in out

def test_recv_out_writes_file(tmp_path, capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan", encoding="utf-8")
    run(["send", "gpt", "do this", "--from", "claude", "--file", str(plan)], c)
    outdir = tmp_path / "received"
    run(["recv", "gpt", "--timeout", "1", "--out", str(outdir)], c)
    saved = outdir / "plan.md"
    assert saved.read_text(encoding="utf-8") == "# Plan"

def test_send_missing_file_errors(capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    rc = run(["send", "gpt", "x", "--from", "claude", "--file", "/no/such/file.md"], c)
    assert rc == 1
    assert "not found" in capsys.readouterr().err

def test_send_binary_file_rejected(tmp_path, capsys):
    c = fakeredis.FakeStrictRedis(decode_responses=True)
    binf = tmp_path / "blob.bin"
    binf.write_bytes(b"\xff\xfe\x00\x01\x80")
    rc = run(["send", "gpt", "x", "--from", "claude", "--file", str(binf)], c)
    assert rc == 1
    assert "text files" in capsys.readouterr().err
