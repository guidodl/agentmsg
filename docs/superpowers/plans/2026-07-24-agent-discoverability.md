# Agent Discoverability (`init` + skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `agentmsg init` command that makes agentmsg discoverable to any harness by writing an idempotent managed block into `AGENTS.md`, plus a bundled Claude Code skill it can install globally.

**Architecture:** A new `src/agentmsg/init.py` module owns all discoverability logic (block rendering, managed-block file writes, skill copy) with no Redis dependency. `cli.py` gains an `init` subparser that short-circuits before any Redis client is created. The canonical skill ships as package data under `src/agentmsg/skill/SKILL.md`.

**Tech Stack:** Python 3.11+, argparse, pytest (+ fakeredis for existing tests, not needed for init).

## Global Constraints

- Python `>=3.11` (uses `str | None` union syntax — match existing style).
- Dependencies limited to `redis>=5.0`; dev adds `pytest>=8.0`, `fakeredis>=2.20`. Do not add new runtime deps.
- No comments unless the *why* is non-obvious.
- No error handling for impossible/internal cases — validate only at boundaries.
- `init` must NOT require or open a Redis connection.
- Managed block markers are exactly `<!-- agentmsg:start -->` and `<!-- agentmsg:end -->`.
- Update `README.md` to document `init` (project rule).

---

### Task 1: `init` module — render the AGENTS.md block

**Files:**
- Create: `src/agentmsg/init.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `START = "<!-- agentmsg:start -->"`, `END = "<!-- agentmsg:end -->"` (module constants).
  - `render_block(name: str) -> str` — returns the full managed block, markers included, with `{name}` substituted. No trailing newline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init.py
from agentmsg import init

def test_render_block_contains_markers_and_name():
    block = init.render_block("copilot")
    assert block.startswith(init.START)
    assert block.rstrip().endswith(init.END)
    assert "`copilot`" in block
    assert "agentmsg send <recipient>" in block
    assert "agentmsg recv copilot --timeout 5" in block
    assert "Do not poll in a loop" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/guido.dilauro/WORKDIR/agentmsg && .venv/bin/pytest tests/test_init.py -v`
Expected: FAIL (ModuleNotFoundError: no module named agentmsg.init)

- [ ] **Step 3: Write minimal implementation**

```python
# src/agentmsg/init.py
START = "<!-- agentmsg:start -->"
END = "<!-- agentmsg:end -->"


def render_block(name: str) -> str:
    return f"""{START}
## Talking to other agents (agentmsg)

You are the **`{name}`** agent. Other AI agents share a local message bus via the `agentmsg` CLI.

- To send: `agentmsg send <recipient> "<message>" --from {name}` (attach a text file with `--file <path>`).
- When the user asks whether another agent messaged you, or to check your inbox: `agentmsg recv {name} --timeout 5`.
- List known agents: `agentmsg agents`.

Only send when the user asks you to message another agent. Do not poll in a loop unless explicitly told to.
{END}"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_init.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentmsg/init.py tests/test_init.py
git commit -m "feat: render agentmsg AGENTS.md instruction block"
```

---

### Task 2: Resolve agent name with fallback chain

**Files:**
- Modify: `src/agentmsg/init.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `render_block` (Task 1).
- Produces:
  - `resolve_name(explicit: str | None, cwd: str) -> str` — returns `explicit` → `$AGENTMSG_AGENT` → `os.path.basename(cwd)`.

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_name_precedence(monkeypatch):
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert init.resolve_name("explicit", "/tmp/proj") == "explicit"
    monkeypatch.setenv("AGENTMSG_AGENT", "envagent")
    assert init.resolve_name(None, "/tmp/proj") == "envagent"
    monkeypatch.delenv("AGENTMSG_AGENT", raising=False)
    assert init.resolve_name(None, "/tmp/proj") == "proj"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_init.py::test_resolve_name_precedence -v`
Expected: FAIL (AttributeError: module has no attribute resolve_name)

- [ ] **Step 3: Write minimal implementation**

Add to `src/agentmsg/init.py`:

```python
import os


def resolve_name(explicit: str | None, cwd: str) -> str:
    return explicit or os.environ.get("AGENTMSG_AGENT") or os.path.basename(cwd)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_init.py::test_resolve_name_precedence -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentmsg/init.py tests/test_init.py
git commit -m "feat: resolve init agent name with fallback chain"
```

---

### Task 3: Idempotent managed-block file write

**Files:**
- Modify: `src/agentmsg/init.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `render_block`, `START`, `END` (Task 1).
- Produces:
  - `write_instructions(path: str, name: str) -> None` — creates/append/replace per the managed-block rules.

**Rules:** file missing → create with just the block. File exists without markers → append block preceded by one blank line. File exists with markers → replace the marker span (inclusive) in place, surrounding bytes unchanged.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_init.py -k write -v`
Expected: FAIL (AttributeError: no attribute write_instructions)

- [ ] **Step 3: Write minimal implementation**

Add to `src/agentmsg/init.py`:

```python
def write_instructions(path: str, name: str) -> None:
    block = render_block(name)
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(block + "\n")
        return
    with open(path, "r", encoding="utf-8") as f:
        existing = f.read()
    if START in existing and END in existing:
        pre = existing[: existing.index(START)]
        post = existing[existing.index(END) + len(END) :]
        updated = pre + block + post
    else:
        sep = "" if existing.endswith("\n") else "\n"
        updated = existing + sep + "\n" + block + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_init.py -k write -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agentmsg/init.py tests/test_init.py
git commit -m "feat: idempotent AGENTS.md managed-block writer"
```

---

### Task 4: Canonical skill file + packaging

**Files:**
- Create: `src/agentmsg/skill/SKILL.md`
- Modify: `pyproject.toml`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `skill_source_path() -> str` in `init.py` — absolute path to the bundled `skill/SKILL.md`.

- [ ] **Step 1: Create the skill file**

```markdown
<!-- src/agentmsg/skill/SKILL.md -->
---
name: agentmsg
description: Use when the user asks to message, send something to, or hear back from another AI agent by name (e.g. "send this to claude", "did copilot reply?", "check my agent inbox"). Sends/receives messages between agents over a local Redis bus via the agentmsg CLI.
---

# agentmsg — talking to other agents

Other AI agents share a local message bus via the `agentmsg` shell CLI. Your agent
name defaults to `$AGENTMSG_AGENT`, or `claude` if unset.

- **Send:** `agentmsg send <recipient> "<message>" --from <me>` — attach a text file with `--file <path>`.
- **Check inbox on demand:** `agentmsg recv <me> --timeout 5` — run this when the user asks whether another agent messaged you.
- **List known agents:** `agentmsg agents`.

Only send when the user asks you to message another agent. Do not poll in a loop
unless the user explicitly asks for a live back-and-forth.
```

- [ ] **Step 2: Write the failing test**

```python
import os

def test_skill_source_path_exists():
    path = init.skill_source_path()
    assert os.path.isfile(path)
    assert path.endswith(os.path.join("skill", "SKILL.md"))
    assert "name: agentmsg" in open(path, encoding="utf-8").read()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_init.py::test_skill_source_path_exists -v`
Expected: FAIL (AttributeError: no attribute skill_source_path)

- [ ] **Step 4: Implement `skill_source_path` and package the data**

Add to `src/agentmsg/init.py`:

```python
def skill_source_path() -> str:
    return os.path.join(os.path.dirname(__file__), "skill", "SKILL.md")
```

Add to `pyproject.toml` after the `[tool.setuptools.packages.find]` block:

```toml
[tool.setuptools.package-data]
agentmsg = ["skill/SKILL.md"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_init.py::test_skill_source_path_exists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agentmsg/skill/SKILL.md src/agentmsg/init.py pyproject.toml tests/test_init.py
git commit -m "feat: bundle canonical agentmsg Claude skill as package data"
```

---

### Task 5: Install skill into a skills dir

**Files:**
- Modify: `src/agentmsg/init.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `skill_source_path` (Task 4).
- Produces:
  - `resolve_skills_dir(explicit: str | None) -> str` — `explicit` → `$CLAUDE_SKILLS_DIR` → `~/.claude/skills`.
  - `install_skill(skills_dir: str) -> str` — copies bundled SKILL.md to `<skills_dir>/agentmsg/SKILL.md`, creating dirs; returns the destination dir. Idempotent (overwrites).

- [ ] **Step 1: Write the failing tests**

```python
def test_resolve_skills_dir_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_SKILLS_DIR", raising=False)
    assert init.resolve_skills_dir(str(tmp_path)) == str(tmp_path)
    monkeypatch.setenv("CLAUDE_SKILLS_DIR", "/env/skills")
    assert init.resolve_skills_dir(None) == "/env/skills"
    monkeypatch.delenv("CLAUDE_SKILLS_DIR", raising=False)
    assert init.resolve_skills_dir(None) == os.path.expanduser("~/.claude/skills")

def test_install_skill_copies_and_overwrites(tmp_path):
    dest = init.install_skill(str(tmp_path))
    copied = os.path.join(dest, "SKILL.md")
    assert os.path.isfile(copied)
    assert "name: agentmsg" in open(copied, encoding="utf-8").read()
    init.install_skill(str(tmp_path))  # re-run is clean
    assert os.path.isfile(copied)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_init.py -k skill -v`
Expected: FAIL (no attribute resolve_skills_dir / install_skill)

- [ ] **Step 3: Write minimal implementation**

Add to `src/agentmsg/init.py` (add `import shutil` at top):

```python
def resolve_skills_dir(explicit: str | None) -> str:
    return explicit or os.environ.get("CLAUDE_SKILLS_DIR") or os.path.expanduser("~/.claude/skills")


def install_skill(skills_dir: str) -> str:
    dest = os.path.join(skills_dir, "agentmsg")
    os.makedirs(dest, exist_ok=True)
    shutil.copyfile(skill_source_path(), os.path.join(dest, "SKILL.md"))
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_init.py -k skill -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentmsg/init.py tests/test_init.py
git commit -m "feat: install bundled skill into resolved skills dir"
```

---

### Task 6: Wire `init` into the CLI

**Files:**
- Modify: `src/agentmsg/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `init.resolve_name`, `init.write_instructions`, `init.resolve_skills_dir`, `init.install_skill` (Tasks 2-5).
- Produces: `agentmsg init [--name] [--file] [--skill] [--skills-dir]` subcommand that never touches Redis.

**Key detail:** In `main()`, handle `init` BEFORE `core.get_client()` so no Redis connection is attempted.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_cli.py
import os
from agentmsg import init as initmod

def test_init_writes_agents_file(tmp_path, capsys):
    target = tmp_path / "AGENTS.md"
    rc = cli.main(["init", "--name", "copilot", "--file", str(target)])
    assert rc == 0
    text = target.read_text(encoding="utf-8")
    assert "`copilot`" in text and initmod.START in text
    assert "wrote instructions" in capsys.readouterr().out

def test_init_with_skill_installs(tmp_path, capsys):
    target = tmp_path / "AGENTS.md"
    skills = tmp_path / "skills"
    rc = cli.main(["init", "--name", "copilot", "--file", str(target),
                   "--skill", "--skills-dir", str(skills)])
    assert rc == 0
    assert (skills / "agentmsg" / "SKILL.md").is_file()
    assert "installed skill" in capsys.readouterr().out

def test_init_does_not_touch_redis(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTMSG_REDIS_URL", "not-a-valid-url")
    target = tmp_path / "AGENTS.md"
    assert cli.main(["init", "--name", "x", "--file", str(target)]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -k init -v`
Expected: FAIL (argparse: invalid choice 'init')

- [ ] **Step 3: Add the subparser**

In `_build_parser()`, after the `agents` subparser and before `return p`:

```python
    it = sub.add_parser("init", help="Write agentmsg instructions into AGENTS.md")
    it.add_argument("--name", dest="name", default=None)
    it.add_argument("--file", dest="file", default="AGENTS.md")
    it.add_argument("--skill", action="store_true")
    it.add_argument("--skills-dir", dest="skills_dir", default=None)
```

- [ ] **Step 4: Handle `init` before the Redis client**

Add `from . import init as initmod` to the imports. In `main()`, immediately after `args = _build_parser().parse_args(argv)` and BEFORE the `try:` that builds the client:

```python
    if args.command == "init":
        name = initmod.resolve_name(args.name, os.getcwd())
        initmod.write_instructions(args.file, name)
        print(f"agentmsg: wrote instructions to {args.file} (agent: {name})")
        if args.skill:
            dest = initmod.install_skill(initmod.resolve_skills_dir(args.skills_dir))
            print(f"agentmsg: installed skill to {dest}/")
        return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -k init -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/agentmsg/cli.py tests/test_cli.py
git commit -m "feat: add init subcommand to write AGENTS.md and install skill"
```

---

### Task 7: Document `init` in the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the finished `init` command (Task 6).
- Produces: nothing (docs).

- [ ] **Step 1: Add an `init` subsection**

Insert after the `## Commands` list, before the `## Example` section:

```markdown
## Making agents aware of agentmsg

A freshly launched agent doesn't know agentmsg exists. `agentmsg init` fixes that
by writing an instruction block into `AGENTS.md` (read by Copilot, opencode, and
other harnesses):

```bash
agentmsg init --name copilot          # writes ./AGENTS.md
agentmsg init --name copilot --skill  # also installs the Claude Code skill
```

- The block is written between `<!-- agentmsg:start -->` / `<!-- agentmsg:end -->`
  markers and is safe to re-run — it updates in place without touching the rest of
  the file.
- `--name` defaults to `$AGENTMSG_AGENT`, then the current directory name.
- `--skill` installs a Claude Code skill into `$CLAUDE_SKILLS_DIR` (default
  `~/.claude/skills/`), so Claude learns the same convention.
```

Add `init` to the command list at the top of `## Commands`:

```
agentmsg init [--name <me>] [--file <path>] [--skill] [--skills-dir <path>]
```

- [ ] **Step 2: Verify rendering**

Run: `sed -n '/Making agents aware/,/Example/p' README.md`
Expected: the new section prints correctly.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document agentmsg init command"
```

---

## Self-Review

**Spec coverage:**
- `init` signature + flags → Tasks 2, 5, 6. ✓
- AGENTS.md managed block content → Task 1. ✓
- File-write rules (create/append/replace) → Task 3. ✓
- Name fallback chain → Task 2. ✓
- Skill bundled + install + dual location → Tasks 4, 5; in-repo canonical copy is `src/agentmsg/skill/SKILL.md`. ✓
- `init` never touches Redis → Task 6 (test `test_init_does_not_touch_redis`). ✓
- Testing bullets → covered across Tasks 1-6. ✓
- README updated → Task 7. ✓

**Placeholder scan:** No TBD/TODO; all steps carry concrete code and commands. ✓

**Type consistency:** `render_block(name)`, `resolve_name(explicit, cwd)`, `write_instructions(path, name)`, `skill_source_path()`, `resolve_skills_dir(explicit)`, `install_skill(skills_dir)` — names/signatures consistent across producing and consuming tasks. `START`/`END` constants referenced consistently. ✓

**Note on `--file` default:** stored as relative `"AGENTS.md"`; Task 6 passes it directly to `write_instructions`, resolved against cwd — matches spec default `./AGENTS.md`.
