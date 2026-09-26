#!/usr/bin/env python3
"""Show what the principal did without the Chief of Staff.

It reads Claude Code transcripts from every profile in cos.json and prints
only the human prompts. A prompt that looks like a correction is marked
with "!". Those marks are where lessons come from. Times are local.

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


def date_arg(text):
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD, for example 2026-01-31")


def count_arg(text):
    try:
        n = int(text)
    except ValueError:
        n = -1
    if n < 0:
        raise argparse.ArgumentTypeError("use a whole number, 0 or more")
    return n


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
    floor = cos_lib.since_floor(since)
    real = cos_lib.real_path(path)
    sessions = []
    for profile, tag, d in found:
        for f in glob.glob(os.path.join(d, "*.jsonl")):
            mtime = cos_lib.safe_mtime(f)
            if mtime is None or (floor is not None and mtime < floor):
                continue
            # Folders like "my-repo" and "my_repo" share one dir name, so
            # keep a session only when its own cwd is this folder.
            file_tag = tag
            cwd = cos_lib.session_cwd(f)
            if cwd:
                file_tag = cos_lib.cwd_tag(cwd, real)
                if not file_tag:
                    continue
            sessions.append((mtime, f, profile, file_tag))
    shown = 0
    # Newest session first, across the main folder and every worktree.
    for _, f, profile, tag in sorted(sessions, reverse=True):
        try:
            prompts = list(cos_lib.human_prompts(f, since))
        except OSError:
            continue
        if not prompts:
            continue
        print("\n## {}  [{}, {}]".format(prompts[0][0], profile, tag))
        for ts, text, is_first, _ in prompts:
            # A correction answers an earlier turn, so it is never the first
            # prompt of a session. The first prompt is the task.
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
    ap = argparse.ArgumentParser(
        description="Show what the principal did without the Chief of Staff.")
    ap.add_argument("project", nargs="?", help="path of the repo (a --list row path works as it is)")
    ap.add_argument("--list", action="store_true", help="list every folder with sessions")
    ap.add_argument("--since", type=date_arg, help="YYYY-MM-DD, usually the date of the last log line")
    ap.add_argument("--days", type=count_arg, help="look back N days instead of --since")
    ap.add_argument("--max", type=count_arg, default=120, help="stop after N prompts (0 = no cap)")
    ap.add_argument("--workspace", default=os.getcwd(),
                    help="the CoS workspace folder (default: the current folder)")
    a = ap.parse_args()
    if a.days is not None and not a.since:
        a.since = cos_lib.since_days(a.days)

    root = cos_lib.find_workspace(a.workspace)
    config, error = cos_lib.read_config(root) if root else ({}, None)
    if not root:
        print("note: {} is not a CoS workspace, so only this session's Claude "
              "profile is read".format(a.workspace), file=sys.stderr)
    elif error:
        print("note: cos.json cannot be read ({}), so only this session's Claude "
              "profile is read".format(" ".join(error.split())), file=sys.stderr)
    profile_list = cos_lib.profiles(config, root)
    if a.list:
        return cmd_list(profile_list, a.since)
    if not a.project:
        ap.error("give a project path, or --list")
    return cmd_project(profile_list, cos_lib.correction_re(config), a.project, a.since, a.max)


if __name__ == "__main__":
    sys.exit(main() or 0)
