#!/usr/bin/env python3
"""SessionEnd hook for a Chief of Staff workspace.

It appends one JSON line to memory/inbox.jsonl in the workspace. It does not
judge the session; it only records signal:
  - when the session ended, why, and which Claude profile ran it;
  - how many new prompts a human typed, and the first one (what it was for);
  - the new prompts that read like a correction (where a lesson hides).

"New" means not recorded before. A resumed session adds to the same
transcript, so the hook keeps the keys of recorded prompts in
memory/.inbox-seen.json and records each prompt once. A session end with no
new human prompt writes nothing.

The Chief of Staff reads the inbox at the next session start and turns each
line into a lesson or a project note. See the cos:session-start skill.

Input: the SessionEnd payload as JSON on stdin, for example
  {"session_id": "abc123", "cwd": "/path/to/workspace",
   "transcript_path": "/path/to/transcript.jsonl", "reason": "other"}

It writes nothing outside a CoS workspace. It always exits 0: a broken hook
must never block a session.
"""

import datetime as dt
import json
import os
import sys
import tempfile

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cos_lib  # noqa: E402

MAX_CORRECTIONS = 6
MAX_CHARS = 200
# Keys kept in memory/.inbox-seen.json. Older keys drop off the front.
MAX_SEEN = 5000


def load_seen(root):
    try:
        with open(os.path.join(root, cos_lib.INBOX_SEEN), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [k for k in data if isinstance(k, str)] if isinstance(data, list) else []


def save_seen(root, keys):
    """Write the key list to a temp file, then swap it in."""
    path = os.path.join(root, cos_lib.INBOX_SEEN)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(keys[-MAX_SEEN:], f)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main():
    payload = cos_lib.read_payload()
    root = cos_lib.workspace_from_hook(payload)
    if not root:
        return
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return
    seen = load_seen(root)
    known = set(seen)
    prompts = [p for p in cos_lib.human_prompts(path) if p[3] not in known]
    if not prompts:
        return  # no new prompt from a human, so there is nothing to learn

    config = cos_lib.load_config(root)
    regex = cos_lib.correction_re(config)
    corrections = [
        text[:MAX_CHARS] for _, text, first, _ in prompts
        if not first and cos_lib.is_correction(regex, text)
    ]
    record = {
        "at": dt.datetime.now().isoformat(timespec="minutes"),
        "session": str(payload.get("session_id") or "")[:8],
        "reason": str(payload.get("reason") or ""),
        "profile": cos_lib.profile_name(config, cos_lib.current_config_dir(), root),
        "prompts": len(prompts),
        "first": prompts[0][1][:MAX_CHARS],
        "corrections": corrections[:MAX_CORRECTIONS],
    }
    with open(os.path.join(root, cos_lib.INBOX), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    save_seen(root, seen + [p[3] for p in prompts])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break the principal's session
    sys.exit(0)
