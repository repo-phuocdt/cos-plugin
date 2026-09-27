"""Shared helpers for the cos plugin scripts.

A CoS workspace is a folder with a `cos.json` and a `memory/` folder. The
cos.json that `/cos:init` writes has the key "cos_workspace". A cos.json that
cannot be read, or is not a JSON object (for example after a typo), still
marks a workspace when memory/ is there, so a typo never turns the hooks off
in silence. A JSON object without the key belongs to some other tool. Every
hook checks this first and does nothing outside a workspace.

Only the Python standard library is used, so the plugin needs no install step.
"""

import datetime as dt
import glob
import hashlib
import json
import os
import re
import shlex
import sys
import unicodedata

CONFIG_NAME = "cos.json"
MARKER_KEY = "cos_workspace"
INBOX = os.path.join("memory", "inbox.jsonl")
# The session-start skill moves the inbox here while it reads it.
INBOX_READING = os.path.join("memory", "inbox.reading.jsonl")
# The SessionEnd hook keeps the keys of prompts it already recorded here, so a
# resumed session never records the same prompt twice.
INBOX_SEEN = os.path.join("memory", ".inbox-seen.json")

# Claude Code stores the transcripts of a folder under
# <config dir>/projects/<name>/. It makes <name> from the folder's real path
# (symlinks resolved, then Unicode NFC form): every UTF-16 code unit that is not an ASCII letter or
# digit becomes "-", so an emoji becomes "--". A name longer than 200
# characters is cut at 200, and "-" plus a hash of the path is added. A
# worktree lives in <repo>/.claude/worktrees/<name>/. Checked on Claude Code
# 2.1.283.
MAX_ENCODED = 200
WORKTREE_DIR = os.path.join(".claude", "worktrees")

# A correction is a prompt that tells the agent it went the wrong way. Only a
# word at the very start of a prompt counts: "Fix the stop button" is a task,
# but "Stop, do it the other way" is a correction. Add words for your own chat
# language in cos.json under "correction_words".
CORRECTION_HEAD = 60
CORRECTION_WORDS = [
    "no", "nope", "wrong", "don't", "dont", "do not", "instead", "actually",
    "revert", "undo", "stop", "why did", "that's not", "thats not", "never",
    "redo",
]

# The one-line prompt that starts a delegate: the Chief of Staff, or a lead
# agent, points it at a task file such as .loop-task.md or .lead-task.md. The
# work is already written down in memory/projects/. So a session that starts
# with this prompt is a delegate session, and every prompt in it is left out:
# later prompts there come from the Chief of Staff or a lead, not from the
# principal.
COS_PROMPT = re.compile(r"^Read (the file )?\.[A-Za-z0-9_-]+-task\.md\b", re.IGNORECASE)

# Text the CLI puts into a user turn. No human typed any of it.
MACHINE_PREFIX = (
    "<local-command", "<system-reminder>", "<task-notification>",
    "Caveat:", "[Request interrupted", "[Image:", "<user-prompt-submit-hook>",
    "Base directory for this skill:", "(Re-invocation of",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>",
)
# A whole turn wrapped in one tag pair, like the CLI's own notices, is machine
# text too, even for a tag this list does not name yet.
MACHINE_TAG = re.compile(r"^<([a-z][\w-]*)(\s[^>]*)?>[\s\S]*</\1>\s*$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# A slash command arrives wrapped in tags. The human words are in <command-args>.
SLASH_PREFIX = ("<command-name>", "<command-message>")
SLASH_NAME = re.compile(r"<command-name>/?([^<]+)</command-name>")
SLASH_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)

# Seconds with a fraction, as in "06:23:00.12Z". Python 3.9 reads only 3 or 6
# fraction digits, so the fraction is padded or cut to 6 first.
FRACTION = re.compile(r"(T\d\d:\d\d:\d\d)\.(\d+)")


def read_payload():
    """Read the hook payload from stdin. Return {} when there is none."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def read_config(root):
    """Read cos.json. Return (config, error).

    config is {} when the file is missing or cannot be read. error is None
    when the file is missing or fine, else a short reason.
    """
    try:
        with open(os.path.join(root, CONFIG_NAME), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as e:
        return {}, str(e) or type(e).__name__
    if not isinstance(data, dict):
        return {}, "the top level is not a JSON object"
    return data, None


def load_config(root):
    return read_config(root)[0]


def config_problems(config):
    """Short notes on cos.json values the scripts have to ignore."""
    notes = []
    items = config.get("profiles")
    if items is not None and not isinstance(items, list):
        notes.append('"profiles" is not a list, so it is ignored')
    elif isinstance(items, list):
        for i, p in enumerate(items):
            if not isinstance(p, dict):
                notes.append('profile {} is not an object, so it is ignored'.format(i + 1))
            elif p.get("config_dir") is not None and not (
                    isinstance(p["config_dir"], str) and p["config_dir"].strip()):
                notes.append('profile {} has a "config_dir" that is not a path, so it is '
                             'ignored'.format(i + 1))
            elif str(p.get("name")) == "unknown":
                notes.append('profile {} is named "unknown", which the hooks use for '
                             'unlisted accounts'.format(i + 1))
    words = config.get("correction_words")
    if words is not None and not (isinstance(words, list)
                                  and all(isinstance(w, str) for w in words)):
        notes.append('"correction_words" is not a list of words, so it is ignored')
    return notes


def find_workspace(path):
    """Return the absolute path when it is a CoS workspace root, else None."""
    if not isinstance(path, str) or not path:
        return None
    root = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(os.path.join(root, CONFIG_NAME)):
        return None
    if not os.path.isdir(os.path.join(root, "memory")):
        return None
    config, error = read_config(root)
    if error or config.get(MARKER_KEY):
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


def uses_default_dir(profile):
    """True for the default profile: a profile with no "config_dir" (or null).
    Its panes start with CLAUDE_CONFIG_DIR unset, so Claude Code uses its
    normal login and keeps its transcripts in ~/.claude."""
    return isinstance(profile, dict) and profile.get("config_dir") is None


def profiles(config, root=None):
    """Return (name, config_dir) for every Claude profile to scan.

    The list comes from "profiles" in cos.json; a relative config_dir is read
    from the workspace root. The default profile (no config_dir) reads
    ~/.claude. With no profiles set, it is the config dir of this process.
    When profiles are set and ~/.claude is not one of them, ~/.claude is added
    as "unknown": a session there ran on an account the principal did not
    list.
    """
    out, seen = [], set()
    items = config.get("profiles")
    for p in items if isinstance(items, list) else []:
        if uses_default_dir(p):
            path = expand("~/.claude")
        elif isinstance(p, dict) and isinstance(p.get("config_dir"), str) \
                and p["config_dir"].strip():
            path = expand(p["config_dir"].strip(), root)
        else:
            continue
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
        if any(unicodedata.east_asian_width(c) in "WF" for c in word) and len(word) > 1:
            # Chinese, Japanese, and similar scripts use no spaces between
            # words, so a longer word may run straight into the next one.
            parts.append(re.escape(word))
        else:
            # Anything else must end at a word edge. For a one-character
            # Chinese word this means it stands alone, so "不" does not
            # flag "不错".
            parts.append(re.escape(word) + r"(?!\w)")
    return re.compile(r"^[\W_]*(?:" + "|".join(parts) + ")", re.IGNORECASE)


def is_correction(regex, text):
    return bool(regex.search(normalize(text)[:CORRECTION_HEAD]))


def utf16_units(text):
    data = text.encode("utf-16-le", "surrogatepass")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


def js_hash(text):
    """The 32-bit string hash Claude Code uses for long names, made positive."""
    h = 0
    for unit in utf16_units(text):
        h = (h * 31 + unit) & 0xFFFFFFFF
    if h >= 2 ** 31:
        h -= 2 ** 32
    return abs(h)


def base36(n):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if not n:
            return out


def slug(path):
    """The path with every UTF-16 unit that is not [A-Za-z0-9] turned to "-"."""
    return "".join(
        chr(u) if u < 128 and chr(u).isalnum() else "-" for u in utf16_units(path))


def real_path(path):
    """The path as Claude Code records it: symlinks resolved, NFC form."""
    return normalize(os.path.realpath(expand(path)))


def encode(path):
    """The transcript dir name Claude Code uses for a folder."""
    real = real_path(path)
    name = slug(real)
    if len(name) <= MAX_ENCODED:
        return name
    return "{}-{}".format(name[:MAX_ENCODED], base36(js_hash(real)))


def project_of(dir_path, name, project):
    """Tell if transcript dir `name` belongs to the folder `project`.

    Return "main", "worktree <name>", or None. The main dir is matched on its
    exact name. Any other dir is first matched on its name, then confirmed
    from the cwd its sessions recorded, because a long name is cut and could
    fit another folder too. Only worktrees under <repo>/.claude/worktrees/
    are found.
    """
    real = real_path(project)
    if name == encode(real):
        return "main"
    trees = os.path.join(real, WORKTREE_DIR) + os.sep
    long_main = len(slug(real)) > MAX_ENCODED and name.startswith(slug(real)[:MAX_ENCODED] + "-")
    if not long_main and not name.startswith(slug(trees)[:MAX_ENCODED]):
        return None
    return cwd_tag(dir_cwd(dir_path), real)


def cwd_tag(cwd, real):
    """Tag a session cwd against a project's real path: "main",
    "worktree <name>", or None when it belongs somewhere else."""
    if not cwd:
        return None
    cwd = real_path(cwd)
    if cwd == real:
        return "main"
    trees = os.path.join(real, WORKTREE_DIR) + os.sep
    if cwd.startswith(trees):
        return "worktree " + cwd[len(trees):].split(os.sep)[0]
    return None


def unwrap(text):
    """Return the human part of a turn, or None if a machine wrote all of it."""
    if text.startswith(SLASH_PREFIX):
        args = SLASH_ARGS.search(text)
        args = args.group(1).strip() if args else ""
        name = SLASH_NAME.search(text)
        name = name.group(1).strip() if name else "?"
        # A slash call with no arguments carries no intent worth reading.
        return "/{} {}".format(name, args) if args else None
    if text.startswith(MACHINE_PREFIX) or MACHINE_TAG.match(text):
        return None
    return text


def local_minute(ts):
    """Transcript times are UTC ("...Z"). Return local time as YYYY-MM-DDTHH:MM."""
    if not isinstance(ts, str) or not ts:
        return ""
    fixed = FRACTION.sub(lambda m: "{}.{}".format(m.group(1), (m.group(2) + "000000")[:6]), ts)
    try:
        t = dt.datetime.fromisoformat(fixed.replace("Z", "+00:00"))
    except ValueError:
        return ts[:16]
    if t.tzinfo is not None:
        t = t.astimezone()
    return t.strftime("%Y-%m-%dT%H:%M")


def human_prompts(jsonl_path, since=None):
    """Yield (local time, text, is_first_of_session, key) for real human turns.

    since is a local date, YYYY-MM-DD. The first human prompt of the session
    is marked even when since hides it. key names the prompt: its uuid in the
    transcript, or a hash of its time and text. A delegate session (its first
    prompt points at a task file) yields nothing.
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
            if not text:
                continue
            if COS_PROMPT.search(text):
                if first:
                    return  # a delegate session: none of it is the principal's
                continue
            is_first, first = first, False
            raw_ts = rec.get("timestamp") if isinstance(rec.get("timestamp"), str) else ""
            key = rec.get("uuid") if isinstance(rec.get("uuid"), str) and rec.get("uuid") else (
                hashlib.sha1((raw_ts + "\n" + text).encode("utf-8")).hexdigest())
            ts = local_minute(raw_ts)
            if since and ts and ts[:10] < since:
                continue
            yield ts, " ".join(text.split()), is_first, key


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
    """The folder a session ran in, read from its first 64 KB."""
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            head = f.read(65536)
    except OSError:
        return None
    for line in head.splitlines():
        if '"cwd"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("cwd"), str) and rec["cwd"]:
            return rec["cwd"]
    return None


def is_delegate_session(jsonl_path):
    """True when the session's first human prompt points at a task file."""
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"user"' not in line:
                    continue
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
                        if isinstance(p, dict) and p.get("type") == "text")
                if not isinstance(content, str):
                    continue
                text = unwrap(content.strip())
                if text:
                    return bool(COS_PROMPT.search(text))
    except OSError:
        pass
    return False


def dir_cwd(dir_path):
    """The cwd of the newest session in a transcript dir that records one."""
    files = []
    for path in glob.glob(os.path.join(dir_path, "*.jsonl")):
        mtime = safe_mtime(path)
        if mtime is not None:
            files.append((mtime, path))
    for _, path in sorted(files, reverse=True):
        cwd = session_cwd(path)
        if cwd:
            return cwd
    return None


def shell_path(path):
    """A path ready to paste into a shell command, with "~" for home.
    Control characters become "?", so a row always stays on one line."""
    path = CONTROL.sub("?", path)
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~/" + shlex.quote(path[len(home) + 1:])
    return shlex.quote(path)


def since_floor(since):
    """Local midnight of a YYYY-MM-DD date, as a timestamp."""
    return dt.datetime.fromisoformat(since).timestamp() if since else None


def since_days(days):
    return str(dt.date.today() - dt.timedelta(days=days))


def list_rows(profile_list, since=None, skip=()):
    """One line per folder with sessions, newest first.

    Each row ends with the folder the newest session ran in, quoted for the
    shell, so it can be passed to catch-up.py as it is. skip holds folders to
    leave out. Delegate sessions are not counted: the Chief of Staff started
    them, so it has seen that work.
    """
    floor = since_floor(since)
    skip_names = {encode(path) for path in skip}
    rows = []
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        for name in safe_listdir(root):
            if name in skip_names:
                continue
            files = []
            for path in glob.glob(os.path.join(root, name, "*.jsonl")):
                mtime = safe_mtime(path)
                if mtime is not None and (floor is None or mtime >= floor) \
                        and not is_delegate_session(path):
                    files.append((mtime, path))
            if not files:
                continue
            last, newest = max(files)
            where = session_cwd(newest)
            where = shell_path(where) if where else name + " (cwd unknown)"
            rows.append((last, profile, where, len(files)))
    return [
        "{:%Y-%m-%d %H:%M}  {:<10} {:>3} sessions  {}".format(
            dt.datetime.fromtimestamp(last), profile, n, where)
        for last, profile, where, n in sorted(rows, reverse=True)
    ]


def transcript_dirs(profile_list, project_path):
    """Yield (profile, tag, dir) for every transcript dir of this folder,
    its worktrees included. tag is "main" or "worktree <name>"."""
    for profile, config_dir in profile_list:
        root = os.path.join(config_dir, "projects")
        for name in safe_listdir(root):
            path = os.path.join(root, name)
            tag = project_of(path, name, project_path)
            if tag:
                yield profile, tag, path


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
