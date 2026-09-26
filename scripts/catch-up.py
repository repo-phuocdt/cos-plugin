#!/usr/bin/env python3
"""Show what the principal did without the Chief of Staff.

It reads Claude Code transcripts from every profile in cos.json and prints
only the human prompts. A prompt that looks like a correction is marked
with "!". Those marks are where lessons come from.

Run it from the workspace folder, so it can read cos.json:
  python3 catch-up.py --list [--since YYYY-MM-DD | --days N]
  python3 catch-up.py <project-path> [--since YYYY-MM-DD] [--max N]

Read the cos:catch-up skill before you use the output.
"""

import argparse
import datetime as dt
import glob
import os
import sys

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cos_lib  # noqa: E402


def cmd_list(profile_list, since):
    lines = cos_lib.list_rows(profile_list, since)
    print("\n".join(lines) if lines else "no sessions in range")
    return 0


def cmd_project(profile_list, regex, path, since, cap):
    found = list(cos_lib.transcript_dirs(profile_list, path))
    if not found:
        print("no transcript dir for {}".format(path), file=sys.stderr)
        print("run --list to see what exists", file=sys.stderr)
        return 1
    floor = dt.datetime.fromisoformat(since).timestamp() if since else None
    shown = 0
    for profile, name, d in found:
        files = glob.glob(os.path.join(d, "*.jsonl"))
        if floor is not None:
            files = [f for f in files if os.path.getmtime(f) >= floor]
        for f in sorted(files, key=os.path.getmtime, reverse=True):
            prompts = list(cos_lib.human_prompts(f, since))
            if not prompts:
                continue
            tag = "main"
            if "--claude-worktrees-" in name:
                tag = "worktree " + name.split("--claude-worktrees-")[-1]
            print("\n## {}  [{}, {}]".format(prompts[0][0], profile, tag))
            for ts, text, is_first in prompts:
                # A correction answers an earlier turn, so it is never the
                # first prompt of a session. The first prompt is the task.
                mark = "!" if (not is_first and cos_lib.is_correction(regex, text)) else " "
                print("{} {} {}".format(mark, ts[11:], text[:220]))
                shown += 1
                if cap and shown >= cap:
                    print("\n[stopped at --max {}]".format(cap))
                    return 0
    if not shown:
        print("no human prompts in range")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", help="absolute path of the repo")
    ap.add_argument("--list", action="store_true", help="list every folder with sessions")
    ap.add_argument("--since", help="YYYY-MM-DD, usually the date of the last log line")
    ap.add_argument("--days", type=int, help="look back N days instead of --since")
    ap.add_argument("--max", type=int, default=120, help="stop after N prompts (0 = no cap)")
    ap.add_argument("--workspace", default=os.getcwd(),
                    help="the CoS workspace folder (default: the current folder)")
    a = ap.parse_args()
    if a.days and not a.since:
        a.since = cos_lib.since_days(a.days)

    root = cos_lib.find_workspace(a.workspace)
    config = cos_lib.load_config(root) if root else {}
    profile_list = cos_lib.profiles(config)
    if a.list:
        return cmd_list(profile_list, a.since)
    if not a.project:
        ap.error("give a project path, or --list")
    return cmd_project(profile_list, cos_lib.correction_re(config), a.project, a.since, a.max)


if __name__ == "__main__":
    sys.exit(main() or 0)
