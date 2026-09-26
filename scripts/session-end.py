#!/usr/bin/env python3
"""SessionEnd hook for a Chief of Staff workspace.

It appends one JSON line to memory/inbox.jsonl in the workspace. It does not
judge the session; it only records signal:
  - when the session ended, why, and which Claude profile ran it;
  - how many new prompts a human typed, and the first one (what it was for);
  - the new prompts that look like a correction (a lesson may be there).

"New" means not recorded before. A resumed session adds to the same
transcript, so the hook keeps the keys of recorded prompts per session in
memory/.inbox-seen.json and records each prompt once. A session end with no
new human prompt writes nothing. A lock on that file keeps two sessions that
end at the same time from losing each other's keys.

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
import time

try:
    import fcntl
except ImportError:  # not on Windows; the lock is then skipped
    fcntl = None

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import cos_lib  # noqa: E402
except Exception:  # a half-updated plugin must not break the session
    cos_lib = None

MAX_CORRECTIONS = 6
MAX_CHARS = 200
# Sessions kept in memory/.inbox-seen.json. The ones used longest ago drop off.
MAX_SESSIONS = 500


def read_seen(f):
    """{session id: {"t": last use, "k": [prompt keys]}} from the open file."""
    f.seek(0)
    try:
        data = json.loads(f.read() or "{}")
    except ValueError:
        return {}
    if isinstance(data, list):  # the older format: one flat list of keys
        return {"": {"t": 0, "k": [k for k in data if isinstance(k, str)]}}
    if not isinstance(data, dict):
        return {}
    return {sid: v for sid, v in data.items()
            if isinstance(v, dict) and isinstance(v.get("k"), list)}


def write_seen(f, seen):
    newest = sorted(seen.items(), key=lambda kv: kv[1].get("t", 0), reverse=True)
    f.seek(0)
    f.truncate()
    json.dump(dict(newest[:MAX_SESSIONS]), f)
    f.flush()


def main():
    if cos_lib is None:
        return
    payload = cos_lib.read_payload()
    root = cos_lib.workspace_from_hook(payload)
    if not root:
        return
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return
    session = str(payload.get("session_id") or os.path.basename(path))

    with open(os.path.join(root, cos_lib.INBOX_SEEN), "a+", encoding="utf-8") as seen_file:
        if fcntl:
            fcntl.flock(seen_file, fcntl.LOCK_EX)
        seen = read_seen(seen_file)
        known = {k for v in seen.values() for k in v["k"]}
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
            "session": session[:8],
            "reason": str(payload.get("reason") or ""),
            "profile": cos_lib.profile_name(config, cos_lib.current_config_dir(), root),
            "prompts": len(prompts),
            "first": prompts[0][1][:MAX_CHARS],
            "corrections": corrections[:MAX_CORRECTIONS],
        }
        with open(os.path.join(root, cos_lib.INBOX), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        entry = seen.setdefault(session, {"t": 0, "k": []})
        entry["t"] = time.time()
        entry["k"] = entry["k"] + [p[3] for p in prompts]
        write_seen(seen_file, seen)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break the principal's session
    sys.exit(0)
