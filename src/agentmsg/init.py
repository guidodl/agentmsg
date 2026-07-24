import os
import shutil

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


def skill_source_path() -> str:
    return os.path.join(os.path.dirname(__file__), "skill", "SKILL.md")


def resolve_name(explicit: str | None, cwd: str) -> str:
    return explicit or os.environ.get("AGENTMSG_AGENT") or os.path.basename(cwd)


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


def resolve_skills_dir(explicit: str | None) -> str:
    return explicit or os.environ.get("CLAUDE_SKILLS_DIR") or os.path.expanduser("~/.claude/skills")


def install_skill(skills_dir: str) -> str:
    dest = os.path.join(skills_dir, "agentmsg")
    os.makedirs(dest, exist_ok=True)
    shutil.copyfile(skill_source_path(), os.path.join(dest, "SKILL.md"))
    return dest
