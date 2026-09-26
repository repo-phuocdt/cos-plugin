"""Shared helpers for the cos plugin scripts.

A CoS workspace is a folder that holds a `cos.json` file. `/cos:init` creates
it. Every hook checks for that file first and does nothing when it is missing.

Only the Python standard library is used, so the plugin needs no install step.
"""

import datetime as dt
import glob
import json
import os
import re
import sys

CONFIG_NAME = "cos.json"
INBOX = os.path.join("memory", "inbox.jsonl")

# Claude Code stores the transcripts of a folder under
# <config dir>/projects/<encoded cwd>/, where every character that is not a
# letter or a digit becomes "-".
ENCODE = re.compile(r"[^A-Za-z0-9]")

# A correction is a prompt that turns the agent around. Only the opening of a
# prompt counts: "do not touch X" late in a task is an instruction, but "no, do
# it the other way" at the front is a correction. Add words for your own chat
# language in cos.json under "correction_words".
CORRECTION_HEAD = 60
CORRECTION_WORDS = [
    "no", "nope", "wrong", "don't", "dont", "do not", "instead", "actually",
    "revert", "undo", "stop", "why did", "that's not", "thats not", "never",
    "redo",
]

# Prompts the Chief of Staff sends to a delegate point at a task file. They
# are already written down in memory/projects/, so they are noise here.
COS_PROMPT = re.compile(r"\.(loop|lead)-(task|answers)\.md", re.IGNORECASE)

# Text the CLI puts into a user turn. No human typed any of it.
MACHINE_PREFIX = (
    "<local-command", "<system-reminder>", "<task-notification>",
    "Caveat:", "[Request interrupted", "[Image:", "<user-prompt-submit-hook>",
    "Base directory for this skill:", "(Re-invocation of",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>",
)

# A slash command arrives wrapped. The human words are inside <command-args>.
SLASH_NAME = re.compile(r"<command-name>/?([^<]+)</command-name>")
SLASH_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def read_payload():
    """Read the hook payload from stdin. Return {} when there is none."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def find_workspace(path):
    """Return the absolute path when it is a CoS workspace root, else None."""
    if not path:
        return None
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(os.path.join(path, CONFIG_NAME)):
        return path
    return None


def load_config(root):
    """Read cos.json. A missing or broken file gives an empty config."""
    try:
        with open(os.path.join(root, CONFIG_NAME), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def expand(path):
    return os.path.abspath(os.path.expanduser(path))


def current_config_dir():
    """The Claude config dir of this process: CLAUDE_CONFIG_DIR or ~/.claude."""
    return expand(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def profiles(config):
    """Return (name, config_dir) for every Claude profile to scan.

    The list comes from "profiles" in cos.json. With no profiles set, it is
    the config dir of this process. When profiles are set and ~/.claude is not
    one of them, ~/.claude is added as "unknown": a session there ran on an
    account the principal did not list.
    """
    out = []
    for p in config.get("profiles") or []:
        if isinstance(p, dict) and isinstance(p.get("config_dir"), str) and p["config_dir"].strip():
            path = expand(p["config_dir"].strip())
            name = str(p.get("name") or os.path.basename(path).lstrip(".") or "default")
            out.append((name, path))
    if not out:
        return [("default", current_config_dir())]
    default = expand("~/.claude")
    if default not in [path for _, path in out]:
        out.append(("unknown", default))
    return out


def profile_name(config, config_dir):
    """Name of the profile that owns config_dir, or "unknown" when cos.json
    does not list it."""
    for name, path in profiles(config):
        if path == config_dir:
            return name
    return "unknown"


def correction_re(config):
    """Regex for a correction: the English words plus cos.json correction_words."""
    extra = config.get("correction_words") or []
    words = CORRECTION_WORDS + [w.strip() for w in extra if isinstance(w, str) and w.strip()]
    alt = "|".join(re.escape(w) for w in words)
    return re.compile(r"(?<!\w)(" + alt + r")(?!\w)", re.IGNORECASE)


def encode(path):
    return ENCODE.sub("-", expand(path))


def unwrap(text):
    """Return the human part of a turn, or None if a machine wrote all of it."""
    if "<command-args>" in text:
        args = SLASH_ARGS.search(text)
        args = args.group(1).strip() if args else ""
        name = SLASH_NAME.search(text)
        name = name.group(1).strip() if name else "?"
        # A slash call with no arguments carries no intent worth reading.
        return "/{} {}".format(name, args) if args else None
    if text.startswith(MACHINE_PREFIX):
        return None
    return text


def human_prompts(jsonl_path, since=None):
    """Yield (timestamp, text, is_first_of_session) for real human turns."""
    first = True
    with open(jsonl_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"user"' not in line:
                continue  # cheap skip before the JSON parse
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "user" or rec.get("isSidechain"):
                continue
            message = rec.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                content = "".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            if not isinstance(content, str):
                continue
            text = unwrap(content.strip())
            if not text or COS_PROMPT.search(text):
                continue
            ts = str(rec.get("timestamp") or "")[:16]
            if since and ts and ts[:10] < since:
                continue
            yield ts, " ".join(text.split()), first
            first = False


def is_correction(regex, text):
    return bool(regex.search(text[:CORRECTION_HEAD]))


def short_name(encoded):
    """Turn an encoded transcript dir name into something a person can read."""
    home = encode("~")
    if encoded == home:
        return "~"
    if encoded.startswith(home + "-"):
        return "~/" + encoded[len(home) + 1:]
    return encoded


def since_days(days):
    return str(dt.date.today() - dt.timedelta(days=days))


def list_rows(profile_list, since=None):
    """One line per folder with sessions, newest first."""
    floor = dt.datetime.fromisoformat(since).timestamp() if since else None
    rows = []
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            files = glob.glob(os.path.join(root, name, "*.jsonl"))
            if floor is not None:
                files = [f for f in files if os.path.getmtime(f) >= floor]
            if not files:
                continue
            last = max(os.path.getmtime(f) for f in files)
            rows.append((last, profile, short_name(name), len(files)))
    return [
        "{:%Y-%m-%d %H:%M}  {:<10} {:>3} sessions  {}".format(
            dt.datetime.fromtimestamp(last), profile, n, name)
        for last, profile, name, n in sorted(rows, reverse=True)
    ]


def transcript_dirs(profile_list, project_path):
    """Every transcript dir for this folder, including its worktrees.

    A worktree under <repo>/.claude/worktrees/ encodes as "<repo>--claude-...",
    so the double dash keeps a sibling folder like "<repo>-old" out.
    """
    want = encode(project_path)
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name == want or name.startswith(want + "--"):
                yield profile, name, os.path.join(root, name)


def inbox_count(root):
    try:
        with open(os.path.join(root, INBOX), encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0
