#!/usr/bin/env python3
"""SessionEnd hook for a Chief of Staff workspace.

It appends one JSON line to memory/inbox.jsonl in the workspace. The line
records signal, not judgement:
  - when the session ended, why, and which Claude profile ran it;
  - how many prompts a human typed, and the first one (what it was for);
  - the prompts that read like a correction (where a lesson hides).

The Chief of Staff reads the inbox at the next session start and turns each
line into a lesson or a project note. See the cos:session-start skill.

Input: the SessionEnd payload as JSON on stdin, for example
  {"session_id": "abc123", "cwd": "/path/to/workspace",
   "transcript_path": "/path/to/transcript.jsonl", "reason": "other"}

Outside a CoS workspace (no cos.json in "cwd") it writes nothing. It always
exits 0: a broken hook must never block a session.
"""

import datetime as dt
import json
import os
import sys

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cos_lib  # noqa: E402

MAX_CORRECTIONS = 6
MAX_CHARS = 200


def main():
    payload = cos_lib.read_payload()
    root = cos_lib.find_workspace(payload.get("cwd") or os.getcwd())
    if not root:
        return
    config = cos_lib.load_config(root)

    prompts = []
    path = payload.get("transcript_path")
    if isinstance(path, str) and os.path.isfile(path):
        prompts = list(cos_lib.human_prompts(path))
    regex = cos_lib.correction_re(config)
    corrections = [
        text[:MAX_CHARS] for _, text, first in prompts
        if not first and cos_lib.is_correction(regex, text)
    ]

    record = {
        "at": dt.datetime.now().isoformat(timespec="minutes"),
        "session": str(payload.get("session_id") or "")[:8],
        "reason": str(payload.get("reason") or ""),
        "profile": cos_lib.profile_name(config, cos_lib.current_config_dir()),
        "prompts": len(prompts),
        "first": prompts[0][1][:MAX_CHARS] if prompts else "",
        "corrections": corrections[:MAX_CORRECTIONS],
    }
    inbox = os.path.join(root, cos_lib.INBOX)
    os.makedirs(os.path.dirname(inbox), exist_ok=True)
    with open(inbox, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break the principal's session
    sys.exit(0)
