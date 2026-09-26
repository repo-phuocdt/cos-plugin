---
name: catch-up
description: Chief of Staff (CoS) workspace only. Learn from work the principal did without you, by reading git history and Claude Code transcripts, and turn it into project notes and lessons. Load when your notes are behind.
---

# Catch up

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this when the principal worked on a repo without you. You did not see it,
so your notes are behind. This page turns that lost work into notes.

It has two halves. Git says **what changed**. The transcript says **what went
wrong**. Lessons come from the second half.

Two paths bring that work to you:

- **Push.** The plugin's SessionStart hook lists every folder with Claude Code
  sessions in the last 7 days, from all profiles in `cos.json`. It is in your
  context at the top of each session (the `cos:session-start` skill, check 5).
- **Pull.** This page. Use it when the list shows your notes are behind, or
  when you need a repo's whole history since a date.

## When to run it

- The principal says "catch up", or asks about a project you have not touched.
- The session-start list shows a project with sessions newer than its last
  log line.

Do not run it every session. It is a read of many files, and it is only worth
it when something really happened.

## Half 1 — git

Git history lives in another repo, so by hard rule 1 in `CLAUDE.md` this is a
job for a scout agent (the `cos:delegation` skill), not for you. Give it the
date of the last `## Log` line in `memory/projects/<slug>.md` and ask for this:

```bash
cd <project-path>
git log --oneline --since=<YYYY-MM-DD> --all
git log --stat --since=<YYYY-MM-DD> --all | head -60
```

This gives branches, commits, and files. It never gives the reason.

## Half 2 — transcripts

The transcripts sit in the Claude config dirs, not in the repo, so you read
them yourself with the plugin's script. It looks in every profile listed in
`cos.json`. When profiles are listed and `~/.claude` is not one of them, it
reads `~/.claude` too and tags those rows `unknown`: that work ran on an
account the principal did not list. Say which project it was.

Run it from this workspace folder:

```bash
# every folder with sessions, newest first (--days N also works)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/catch-up.py" --list --since <YYYY-MM-DD>

# one repo, its worktrees included
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/catch-up.py" <project-path> --since <YYYY-MM-DD> --max 120
```

Each `--list` row ends with a folder path; pass it to the second command in
double quotes, since a path can hold spaces. The script prints only human prompts. Times are local. It drops tool output, text the CLI
injected, and the prompts you yourself sent to a delegate (the ones that point
at `.loop-task.md` or `.lead-task.md`). A slash command is unwrapped, so
`/fix make the modal close` shows as one line.

A prompt marked `!` is a **correction**: the principal turned the agent around.
Read those first. Two corrections in a row on the same subject is a lesson.

The mark is a guess from words like "no", "instead", or "wrong" at the start
of a prompt. Words in the principal's own language go in `cos.json` under
`correction_words`. The mark is right often, not always. Read the line before
you trust it.

## What you write, and where

| What you saw | Goes to |
|---|---|
| A new convention, trap, or command for that repo | `memory/projects/<slug>.md` |
| A decision the principal made | that project's `## Log`, one line |
| An agent or tool that failed in a way that repeats | `memory/lessons.md` |
| A repo with real work but no project file | ask the principal if you should own it |

Three rules:

1. **Write conclusions, not transcript.** Never paste raw prompt lines into a
   note. One line that says the rule beats ten lines of history.
2. **Never copy a secret.** Prompts can hold tokens, keys, and URLs with
   credentials. If a prompt you want to quote has one, write the lesson without
   it.
3. **Ask before you guess a reason.** The transcript shows what was said, not
   why. If the why matters and is not written, ask the principal in one line.

## What this cannot see

- Work done outside Claude Code. No transcript, no signal.
- Work on a profile that is not in `cos.json` and not in `~/.claude`.
- Why a decision was made, when the principal decided it in their head.
- Anything before the oldest session file on this machine.

Say so plainly when the picture has a hole. Do not fill it with a guess.
