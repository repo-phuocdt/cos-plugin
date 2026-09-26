#!/usr/bin/env python3
"""SessionStart hook for a Chief of Staff workspace.

It adds up to three things to the new session's context:
  - one warning line when cos.json cannot be read, or holds values the
    hooks must ignore;
  - the folders with Claude Code sessions in the last 7 days, from every
    profile listed in cos.json (work the Chief of Staff may not have seen).
    The workspace itself is left out;
  - how many records wait in memory/inbox.jsonl.

Outside a CoS workspace it prints nothing. It always exits 0: a broken hook
must never block a session.
"""

import json
import os
import sys

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import cos_lib  # noqa: E402
except Exception:  # a half-updated plugin must not break the session
    cos_lib = None

DAYS = 7
MAX_ROWS = 12

HEAD = (
    "Claude Code sessions on this machine, all profiles in cos.json, last {days} "
    "days. The Chief of Staff did not see most of this work.\n"
)
MORE = "... and {n} more folder(s). Run the catch-up script with --list to see all.\n"
TAIL = (
    "\nCompare each row with memory/index.md:\n"
    "- a project you own, with sessions newer than its last Log line -> your notes are behind\n"
    "- a folder with many sessions and no file in memory/projects/ -> ask if you should own it\n"
    "- a row from the \"unknown\" profile -> that work ran on an account not listed in cos.json\n"
    "Say it in one line. To read what was said, use the cos:catch-up skill.\n"
)
WARNING = "WARNING: cos.json {problem}. Fix it; until then the hooks use default settings.\n"
INBOX = (
    "\nINBOX: {n} session record(s) wait in memory/inbox.jsonl (and in "
    "memory/inbox.reading.jsonl, if a past session stopped halfway). The SessionEnd "
    "hook wrote one per past session in this workspace, with its first prompt "
    "and any correction the principal made. Turn them into a lesson or a "
    "project note, then clear the inbox. See the cos:session-start skill.\n"
)


def main():
    if cos_lib is None:
        return
    payload = cos_lib.read_payload()
    root = cos_lib.workspace_from_hook(payload)
    if not root:
        return
    config, error = cos_lib.read_config(root)
    if error:
        problem = "cannot be read ({})".format(" ".join(error.split()))
    else:
        problem = "; ".join(cos_lib.config_problems(config))
    rows = cos_lib.list_rows(
        cos_lib.profiles(config, root), cos_lib.since_days(DAYS), skip={root})
    n = cos_lib.inbox_count(root)
    if not rows and not n and not problem:
        return
    ctx = WARNING.format(problem=problem) if problem else ""
    if rows:
        ctx += HEAD.format(days=DAYS) + "\n".join(rows[:MAX_ROWS]) + "\n"
        if len(rows) > MAX_ROWS:
            ctx += MORE.format(n=len(rows) - MAX_ROWS)
        ctx += TAIL
    if n:
        ctx += INBOX.format(n=n)
    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": ctx}}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break the principal's session
    sys.exit(0)
