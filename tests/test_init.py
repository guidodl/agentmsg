from agentmsg import init

def test_render_block_contains_markers_and_name():
    block = init.render_block("copilot")
    assert block.startswith(init.START)
    assert block.rstrip().endswith(init.END)
    assert "`copilot`" in block
    assert "agentmsg send <recipient>" in block
    assert "agentmsg recv copilot --timeout 5" in block
    assert "Do not poll in a loop" in block
