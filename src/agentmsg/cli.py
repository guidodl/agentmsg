import argparse
import json
import os
import sys

import redis

from . import core


def resolve_sender(explicit: str | None) -> str:
    return explicit or os.environ.get("AGENTMSG_AGENT") or "anon"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentmsg", description="Cross-agent messaging over local Redis")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("send", help="Send a message to another agent")
    s.add_argument("to")
    s.add_argument("message")
    s.add_argument("--from", dest="sender", default=None)
    s.add_argument("--file", dest="file", default=None)

    r = sub.add_parser("recv", help="Receive next message (blocking)")
    r.add_argument("me")
    r.add_argument("--timeout", type=int, default=5)
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", dest="out", default=None)

    pk = sub.add_parser("peek", help="Show inbox without consuming")
    pk.add_argument("me")
    pk.add_argument("--json", action="store_true")

    sub.add_parser("agents", help="List known agents")
    return p


def _print_message(env: dict, as_json: bool, out_dir: str | None) -> None:
    if as_json:
        print(json.dumps(env))
        return
    print(f"[{env['from']}] {env['body']}")
    att = env.get("attachment")
    if att:
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, att["filename"])
            with open(path, "w", encoding="utf-8") as f:
                f.write(att["content"])
            print(f"(attachment saved to {path})")
        else:
            print(f"--- attachment: {att['filename']} ---")
            print(att["content"])


def _read_attachment(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"agentmsg: file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError("agentmsg: only text files are supported (file is not valid UTF-8)")
    return {"filename": os.path.basename(path), "content": content}


def _redis_error_msg() -> str:
    url = os.environ.get("AGENTMSG_REDIS_URL") or core.DEFAULT_URL
    return f"agentmsg: cannot reach Redis at {url} — is it running? try 'brew services start redis'"


def main(argv: list[str] | None = None, _client=None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        client = _client if _client is not None else core.get_client()
    except redis.RedisError:
        print(_redis_error_msg(), file=sys.stderr)
        return 1

    try:
        if args.command == "send":
            attachment = _read_attachment(args.file) if args.file else None
            sender = resolve_sender(args.sender)
            core.send_message(client, sender, args.to, args.message, attachment)
            return 0
        if args.command == "recv":
            env = core.recv_message(client, args.me, timeout=args.timeout)
            if env is None:
                if args.json:
                    print("{}")
                return 0
            _print_message(env, args.json, args.out)
            return 0
        if args.command == "peek":
            msgs = core.peek_inbox(client, args.me)
            if args.json:
                print(json.dumps(msgs))
            else:
                for env in msgs:
                    print(f"[{env['from']}] {env['body']}")
            return 0
        if args.command == "agents":
            for a in core.list_agents(client):
                print(f"{a['agent']}\t{a['last_seen']}")
            return 0
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    except redis.RedisError:
        print(_redis_error_msg(), file=sys.stderr)
        return 1
    return 0
