#!/usr/bin/env python3
"""SessionStart hook for a Chief of Staff workspace.

It adds two things to the new session's context:
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
import cos_lib  # noqa: E402

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
INBOX = (
    "\nINBOX: {n} session record(s) wait in memory/inbox.jsonl. The SessionEnd "
    "hook wrote one per past session in this workspace, with its first prompt "
    "and any correction the principal made. Turn them into a lesson or a "
    "project note, then clear the inbox. See the cos:session-start skill.\n"
)


def main():
    payload = cos_lib.read_payload()
    root = cos_lib.workspace_from_hook(payload)
    if not root:
        return
    config = cos_lib.load_config(root)
    rows = cos_lib.list_rows(
        cos_lib.profiles(config, root), cos_lib.since_days(DAYS),
        skip={cos_lib.encode(root)})
    n = cos_lib.inbox_count(root)
    if not rows and not n:
        return
    ctx = ""
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
