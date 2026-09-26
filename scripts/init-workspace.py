#!/usr/bin/env python3
"""Create a Chief of Staff workspace in a folder. The /cos:init skill runs it.

It never overwrites a file. A file that already exists is kept as it is, so
running it twice is safe.

Example:
  python3 init-workspace.py --dir ~/cos --name "Chief of Staff" \\
      --language English --address you \\
      --profile work=~/.claude-work --runtime claude --runtime codex
"""

import argparse
import json
import os
import sys

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
    ("lessons.md.tmpl", os.path.join("memory", "lessons.md")),
]
SETTINGS = os.path.join(".claude", "settings.json")
# Built-in sub-agents are off in a workspace: the Chief of Staff starts other
# agents only through Herdr (see the cos:delegation skill).
DENY = ["Task", "Agent"]

DEFAULTS = {
    "name": "Chief of Staff",
    "language": "English",
    "address": "you",
    "runtime": ["claude"],
}


def one_line(value):
    """Answers go into Markdown and JSON. Keep each one on a single line."""
    return " ".join(str(value).split())


def parse_profile(text):
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=CONFIG_DIR, for example work=~/.claude-work")
    name, path = text.split("=", 1)
    name, path = one_line(name), path.strip()
    if not name or not path:
        raise argparse.ArgumentTypeError("use NAME=CONFIG_DIR, for example work=~/.claude-work")
    return {"name": name, "config_dir": path}


def render(template, values):
    with open(os.path.join(TEMPLATES, template), encoding="utf-8") as f:
        text = f.read()
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write_new(root, rel, text, report):
    path = os.path.join(root, rel)
    if os.path.exists(path):
        report.append(("kept", rel))
        return
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    report.append(("created", rel))


def merge_settings(root, report):
    """Create .claude/settings.json, or add the deny rules to the one that exists."""
    path = os.path.join(root, SETTINGS)
    if not os.path.exists(path):
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    report.append(("updated (deny " + ", ".join(missing) + ")", SETTINGS))


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

    values = {
        "agent_name": one_line(a.name) or DEFAULTS["name"],
        "language": one_line(a.language) or DEFAULTS["language"],
        "principal": one_line(a.address) or DEFAULTS["address"],
    }
    profile_list = a.profile or [{"name": "default", "config_dir": cos_lib.current_config_dir()}]
    runtimes = [one_line(r) for r in a.runtime if one_line(r)] or DEFAULTS["runtime"]

    root = os.path.abspath(os.path.expanduser(a.dir))
    os.makedirs(root, exist_ok=True)
    report = []

    config = {
        "agent_name": values["agent_name"],
        "language": values["language"],
        "principal": values["principal"],
        "profiles": profile_list,
        "runtimes": runtimes,
        "correction_words": [],
    }
    write_new(root, cos_lib.CONFIG_NAME, json.dumps(config, indent=2, ensure_ascii=False) + "\n", report)
    for template, rel in FILES:
        write_new(root, rel, render(template, values), report)
    write_new(root, cos_lib.INBOX, "", report)
    merge_settings(root, report)

    print("Chief of Staff workspace: " + root)
    for state, rel in report:
        print("  {:<8} {}".format(state, rel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
