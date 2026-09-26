"""Shared helpers for the cos plugin scripts.

A CoS workspace is a folder with a `cos.json` that `/cos:init` wrote (it has
the key "cos_workspace") and a `memory/` folder. Every hook checks for both
first and does nothing when either is missing.

Only the Python standard library is used, so the plugin needs no install step.
"""

import datetime as dt
import glob
import json
import os
import re
import sys
import unicodedata

CONFIG_NAME = "cos.json"
MARKER_KEY = "cos_workspace"
INBOX = os.path.join("memory", "inbox.jsonl")
# The session-start skill moves the inbox here while it reads it.
INBOX_READING = os.path.join("memory", "inbox.reading.jsonl")

# Claude Code stores the transcripts of a folder under
# <config dir>/projects/<encoded cwd>/, where every character that is not a
# letter or a digit becomes "-". A name longer than 200 characters is cut at
# 200 and gets "-<hash>" at the end. A worktree under <repo>/.claude/worktrees/
# encodes as "<repo>--claude-worktrees-<name>".
ENCODE = re.compile(r"[^A-Za-z0-9]")
MAX_ENCODED = 200
WORKTREE = "--claude-worktrees-"

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

# The one-line prompt the Chief of Staff sends to a delegate. The task itself
# is already written down in memory/projects/, so this prompt is noise here.
COS_PROMPT = re.compile(r"^Read (the file )?\.(loop|lead)-task\.md\b", re.IGNORECASE)

# Text the CLI puts into a user turn. No human typed any of it.
MACHINE_PREFIX = (
    "<local-command", "<system-reminder>", "<task-notification>",
    "Caveat:", "[Request interrupted", "[Image:", "<user-prompt-submit-hook>",
    "Base directory for this skill:", "(Re-invocation of",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>",
)

# A slash command arrives wrapped in tags. The human words are in <command-args>.
SLASH_PREFIX = ("<command-name>", "<command-message>")
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


def load_config(root):
    """Read cos.json. Return {} when it is missing, broken, or not an object."""
    try:
        with open(os.path.join(root, CONFIG_NAME), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def find_workspace(path):
    """Return the absolute path when it is a CoS workspace root, else None.

    Some other tool's cos.json does not count: the file must hold the marker
    key that /cos:init writes, and memory/ must exist.
    """
    if not isinstance(path, str) or not path:
        return None
    root = os.path.abspath(os.path.expanduser(path))
    if load_config(root).get(MARKER_KEY) and os.path.isdir(os.path.join(root, "memory")):
        return root
    return None


def workspace_from_hook(payload):
    """The workspace of a hook run: the session's cwd, else the project dir."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    return find_workspace(cwd) or find_workspace(os.environ.get("CLAUDE_PROJECT_DIR"))


def expand(path, base=None):
    """Absolute path. "~" is expanded; a relative path is read from base."""
    path = os.path.expanduser(path)
    if base and not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.abspath(path)


def current_config_dir():
    """The Claude config dir of this process: CLAUDE_CONFIG_DIR or ~/.claude."""
    return expand(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")


def profiles(config, root=None):
    """Return (name, config_dir) for every Claude profile to scan.

    The list comes from "profiles" in cos.json; a relative config_dir is read
    from the workspace root. With no profiles set, it is the config dir of this
    process. When profiles are set and ~/.claude is not one of them, ~/.claude
    is added as "unknown": a session there ran on an account the principal did
    not list.
    """
    out, seen = [], set()
    items = config.get("profiles")
    for p in items if isinstance(items, list) else []:
        if not isinstance(p, dict) or not isinstance(p.get("config_dir"), str):
            continue
        if not p["config_dir"].strip():
            continue
        path = expand(p["config_dir"].strip(), root)
        if os.path.realpath(path) in seen:
            continue
        seen.add(os.path.realpath(path))
        name = str(p.get("name") or os.path.basename(path).lstrip(".") or "default")
        out.append((name, path))
    if not out:
        return [("default", current_config_dir())]
    default = expand("~/.claude")
    if os.path.realpath(default) not in seen:
        out.append(("unknown", default))
    return out


def profile_name(config, config_dir, root=None):
    """Name of the profile that owns config_dir, or "unknown" when cos.json
    does not list it. Paths are compared after symlinks are resolved."""
    real = os.path.realpath(config_dir)
    for name, path in profiles(config, root):
        if os.path.realpath(path) == real:
            return name
    return "unknown"


def normalize(text):
    return unicodedata.normalize("NFC", text)


def correction_re(config):
    """Regex for a correction: the English words plus cos.json correction_words."""
    extra = config.get("correction_words")
    extra = extra if isinstance(extra, list) else []
    words = CORRECTION_WORDS + [w.strip() for w in extra if isinstance(w, str) and w.strip()]
    parts = []
    for word in words:
        word = normalize(word)
        if any(unicodedata.east_asian_width(c) in "WF" for c in word):
            # Chinese, Japanese, and similar scripts use no spaces between
            # words, so a word boundary check would never match. Match the
            # word only at the start of the prompt instead.
            parts.append(r"^[\W_]*" + re.escape(word))
        else:
            parts.append(r"(?<!\w)" + re.escape(word) + r"(?!\w)")
    return re.compile("|".join(parts), re.IGNORECASE)


def is_correction(regex, text):
    return bool(regex.search(normalize(text)[:CORRECTION_HEAD]))


def encode(path):
    return ENCODE.sub("-", expand(path))


def dir_matches(name, want):
    """True when transcript dir `name` belongs to the folder encoded as `want`,
    or to one of its worktrees. Long names are compared on their first 200
    characters, because that is all Claude Code keeps."""
    if len(want) > MAX_ENCODED:
        return name.startswith(want[:MAX_ENCODED] + "-")
    return name == want or name.startswith((want + WORKTREE)[:MAX_ENCODED])


def unwrap(text):
    """Return the human part of a turn, or None if a machine wrote all of it."""
    if text.startswith(SLASH_PREFIX):
        args = SLASH_ARGS.search(text)
        args = args.group(1).strip() if args else ""
        name = SLASH_NAME.search(text)
        name = name.group(1).strip() if name else "?"
        # A slash call with no arguments carries no intent worth reading.
        return "/{} {}".format(name, args) if args else None
    if text.startswith(MACHINE_PREFIX):
        return None
    return text


def local_minute(ts):
    """Transcript times are UTC ("...Z"). Return local time as YYYY-MM-DDTHH:MM."""
    if not isinstance(ts, str) or not ts:
        return ""
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts[:16]
    if t.tzinfo is not None:
        t = t.astimezone()
    return t.strftime("%Y-%m-%dT%H:%M")


def human_prompts(jsonl_path, since=None):
    """Yield (local time, text, is_first_of_session) for real human turns.

    since is a local date, YYYY-MM-DD. The first human prompt of the session
    is marked even when since hides it.
    """
    first = True
    with open(jsonl_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"user"' not in line:
                continue  # cheap skip before the JSON parse
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "user":
                continue
            if rec.get("isSidechain") or rec.get("isMeta") or rec.get("isCompactSummary"):
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
            is_first, first = first, False
            ts = local_minute(rec.get("timestamp"))
            if since and ts and ts[:10] < since:
                continue
            yield ts, " ".join(text.split()), is_first


def safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def safe_listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def session_cwd(jsonl_path):
    """The folder a session ran in, read from its first records."""
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 50:
                    break
                if '"cwd"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and isinstance(rec.get("cwd"), str):
                    return rec["cwd"]
    except OSError:
        pass
    return None


def display_path(path):
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


def since_floor(since):
    """Local midnight of a YYYY-MM-DD date, as a timestamp."""
    return dt.datetime.fromisoformat(since).timestamp() if since else None


def since_days(days):
    return str(dt.date.today() - dt.timedelta(days=days))


def list_rows(profile_list, since=None, skip=()):
    """One line per folder with sessions, newest first.

    Each row shows the folder the newest session ran in, so it can be passed
    to catch-up.py as it is. skip holds encoded folder names to leave out,
    with their worktrees.
    """
    floor = since_floor(since)
    rows = []
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        for name in safe_listdir(root):
            if any(dir_matches(name, want) for want in skip):
                continue
            files = []
            for path in glob.glob(os.path.join(root, name, "*.jsonl")):
                mtime = safe_mtime(path)
                if mtime is not None and (floor is None or mtime >= floor):
                    files.append((mtime, path))
            if not files:
                continue
            last, newest = max(files)
            where = session_cwd(newest)
            where = display_path(where) if where else name
            rows.append((last, profile, where, len(files)))
    return [
        "{:%Y-%m-%d %H:%M}  {:<10} {:>3} sessions  {}".format(
            dt.datetime.fromtimestamp(last), profile, n, where)
        for last, profile, where, n in sorted(rows, reverse=True)
    ]


def transcript_dirs(profile_list, project_path):
    """Every transcript dir for this folder, including its worktrees."""
    want = encode(project_path)
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        for name in safe_listdir(root):
            if dir_matches(name, want):
                yield profile, name, os.path.join(root, name)


def inbox_count(root):
    """Records waiting in the inbox, plus any left in a half-read copy."""
    n = 0
    for rel in (INBOX, INBOX_READING):
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
                n += sum(1 for line in f if line.strip())
        except OSError:
            pass
    return n
