from agentmsg import init

def test_render_block_contains_markers_and_name():
    block = init.render_block("copilot")
    assert block.startswith(init.START)
    assert block.rstrip().endswith(init.END)
    assert "`copilot`" in block
    assert "agentmsg send <recipient>" in block
    assert "agentmsg recv copilot --timeout 5" in block
    assert "Do not poll in a loop" in block


def test_resolve_name_precedence(monkeypatch):
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert init.resolve_name("explicit", "/tmp/proj") == "explicit"
    monkeypatch.setenv("AGENTMSG_AGENT", "envagent")
    assert init.resolve_name(None, "/tmp/proj") == "envagent"
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert init.resolve_name(None, "/tmp/proj") == "proj"


def test_write_creates_file(tmp_path):
    p = tmp_path / "AGENTS.md"
    init.write_instructions(str(p), "copilot")
    text = p.read_text(encoding="utf-8")
    assert text.startswith(init.START)
    assert "`copilot`" in text

def test_write_appends_when_no_markers(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Existing\n\nkeep me\n", encoding="utf-8")
    init.write_instructions(str(p), "copilot")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("# Existing")
    assert "keep me" in text
    assert init.START in text
    assert text.count(init.START) == 1

def test_write_replaces_in_place(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("head\n\n", encoding="utf-8")
    init.write_instructions(str(p), "old")
    init.write_instructions(str(p), "new")
    text = p.read_text(encoding="utf-8")
    assert text.count(init.START) == 1
    assert "`new`" in text
    assert "`old`" not in text
    assert text.startswith("head")
