#!/usr/bin/env python3
"""Create a Chief of Staff workspace in a folder. The /cos:init skill runs it.

It never overwrites a file. A file that already exists is kept as it is, so
running it again only adds the files that are missing. cos.json is written
last: it marks the folder as a workspace, so a run that fails halfway leaves
no marker behind.

Example:
  python3 init-workspace.py --dir ~/cos --name 'Chief of Staff' \\
      --language English --address you \\
      --profile work=/home/me/.claude-work --runtime claude --runtime codex
"""

import argparse
import json
import os
import re
import stat
import sys
import tempfile

# Write no __pycache__ into the plugin folder; the plugin root can be read-only
# and it changes on every update.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cos_lib  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

# (template file, path in the workspace)
FILES = [
    ("CLAUDE.md.tmpl", "CLAUDE.md"),
    ("identity.md.tmpl", "identity.md"),
    ("index.md.tmpl", os.path.join("memory", "index.md")),
    ("project.md.tmpl", os.path.join("memory", "projects", "_template.md")),
]
# Files that start empty.
EMPTY = [os.path.join("memory", "lessons.md"), cos_lib.INBOX]
SETTINGS = os.path.join(".claude", "settings.json")
GITIGNORE = ".gitignore"
# The inbox files hold prompt text, so git must not pick them up by mistake.
IGNORE_LINES = [cos_lib.INBOX, cos_lib.INBOX_READING, cos_lib.INBOX_SEEN]
IGNORE_HEAD = "# Chief of Staff: these files hold prompt text. Keep them out of git."
UNSET_VAR = re.compile(r"\$(\w+|\{\w+\})")
# Built-in sub-agents are off in a workspace: the Chief of Staff starts other
# agents only through Herdr (see the cos:delegation skill).
DENY = ["Task", "Agent"]
PLACEHOLDER = re.compile(r"\{\{(agent_name|language|address)\}\}")

DEFAULTS = {
    "name": "Chief of Staff",
    "language": "English",
    "address": "you",
    "runtime": ["claude"],
}


def one_line(value):
    """Answers go into Markdown and JSON. Keep each one on a single line, and
    drop "@" at the start of a word so CLAUDE.md never reads it as a file
    import."""
    text = " ".join(str(value).split())
    return re.sub(r"(^|\s)@+(?=\S)", r"\1", text).strip()


def parse_profile(text):
    name, sep, path = text.partition("=")
    name, path = one_line(name), os.path.expandvars(path.strip())
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError("use NAME=CONFIG_DIR, for example work=/home/me/.claude-work")
    unset = UNSET_VAR.search(path)
    if unset:
        raise argparse.ArgumentTypeError(
            "{} is not set, so the profile path {} is wrong. Set it, or use a full path."
            .format(unset.group(0), path))
    return name, path


def render(template, values):
    with open(os.path.join(TEMPLATES, template), encoding="utf-8") as f:
        text = f.read()
    # One pass, so an answer that holds "{{...}}" is never replaced again.
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def write_new(root, rel, text, report):
    """Write a new file. Keep any file, folder, or symlink that is already there."""
    path = os.path.join(root, rel)
    if os.path.lexists(path):
        report.append(("kept", rel))
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as f:
            f.write(text)
    except FileExistsError:
        report.append(("kept", rel))
        return
    report.append(("created", rel))


def merge_settings(root, report):
    """Create .claude/settings.json, or add the deny rules to the one that exists."""
    path = os.path.join(root, SETTINGS)
    if not os.path.lexists(path):
        text = json.dumps({"permissions": {"deny": DENY}}, indent=2) + "\n"
        write_new(root, SETTINGS, text, report)
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        deny = data.setdefault("permissions", {}).setdefault("deny", [])
        if not isinstance(deny, list):
            raise ValueError("permissions.deny is not a list")
    except (OSError, ValueError, AttributeError):
        report.append(("SKIPPED (cannot read it; add the deny rules by hand)", SETTINGS))
        return
    missing = [rule for rule in DENY if rule not in deny]
    if not missing:
        report.append(("kept", SETTINGS))
        return
    deny.extend(missing)
    # Write a temp file, then swap it in, so a crash never leaves half a file.
    target = os.path.realpath(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, stat.S_IMODE(os.stat(target).st_mode))
        os.replace(tmp, target)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    report.append(("updated (deny " + ", ".join(missing) + ")", SETTINGS))


def update_gitignore(root, report):
    """Add the inbox files to .gitignore. Only appends; never changes a line."""
    path = os.path.join(root, GITIGNORE)
    lines = [rel.replace(os.sep, "/") for rel in IGNORE_LINES]
    if not os.path.lexists(path):
        write_new(root, GITIGNORE, "\n".join([IGNORE_HEAD] + lines) + "\n", report)
        return
    if os.path.islink(path) or not os.path.isfile(path):
        report.append(("SKIPPED (not a plain file; add the inbox lines by hand)", GITIGNORE))
        return
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    have = {line.strip() for line in text.splitlines()}
    missing = [line for line in lines if line not in have]
    if not missing:
        report.append(("kept", GITIGNORE))
        return
    with open(path, "a", encoding="utf-8") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write("\n".join([IGNORE_HEAD] + missing) + "\n")
    report.append(("updated (+{} lines)".format(len(missing)), GITIGNORE))


def main():
    ap = argparse.ArgumentParser(description="Create a Chief of Staff workspace.")
    ap.add_argument("--dir", default=os.getcwd(), help="workspace folder (default: current folder)")
    ap.add_argument("--name", default=DEFAULTS["name"], help="the agent's name")
    ap.add_argument("--language", default=DEFAULTS["language"], help="chat language with the principal")
    ap.add_argument("--address", default=DEFAULTS["address"], help="how the agent addresses the principal")
    ap.add_argument("--profile", action="append", type=parse_profile, default=[],
                    help="a Claude profile as NAME=CONFIG_DIR (repeat for more)")
    ap.add_argument("--runtime", action="append", default=[],
                    help="a Herdr agent kind the agent may start (repeat for more)")
    a = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(a.dir))
    values = {
        "agent_name": one_line(a.name) or DEFAULTS["name"],
        "language": one_line(a.language) or DEFAULTS["language"],
        "address": one_line(a.address) or DEFAULTS["address"],
    }
    # Store full paths: a pane gets CLAUDE_CONFIG_DIR=<config_dir>, and a shell
    # does not always expand "~" there.
    profile_list = [{"name": name, "config_dir": cos_lib.expand(path, root)}
                    for name, path in a.profile]
    if not profile_list:
        profile_list = [{"name": "default", "config_dir": cos_lib.current_config_dir()}]
    runtimes = [one_line(r) for r in a.runtime if one_line(r)] or DEFAULTS["runtime"]
    config = {
        cos_lib.MARKER_KEY: 1,
        "agent_name": values["agent_name"],
        "language": values["language"],
        "address": values["address"],
        "profiles": profile_list,
        "runtimes": runtimes,
        "correction_words": [],
    }

    marker = os.path.join(root, cos_lib.CONFIG_NAME)
    if os.path.lexists(marker):
        old, error = cos_lib.read_config(root)
        if error:
            print("error: {} is broken ({}). Fix it, then run init again."
                  .format(marker, " ".join(error.split())), file=sys.stderr)
            return 1
        if not old.get(cos_lib.MARKER_KEY):
            print("error: {} belongs to some other tool (no \"{}\" key). Use another "
                  "folder for the workspace.".format(marker, cos_lib.MARKER_KEY), file=sys.stderr)
            return 1

    report = []
    try:
        os.makedirs(root, exist_ok=True)
        for template, rel in FILES:
            write_new(root, rel, render(template, values), report)
        for rel in EMPTY:
            write_new(root, rel, "", report)
        merge_settings(root, report)
        update_gitignore(root, report)
        write_new(root, cos_lib.CONFIG_NAME,
                  json.dumps(config, indent=2, ensure_ascii=False) + "\n", report)
    except OSError as e:
        for state, rel in report:
            print("  {:<8} {}".format(state, rel))
        print("error: {}. Fix it and run init again; it keeps what exists.".format(e),
              file=sys.stderr)
        return 1

    print("Chief of Staff workspace: " + root)
    for state, rel in report:
        print("  {:<8} {}".format(state, rel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
