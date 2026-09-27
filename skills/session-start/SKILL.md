---
name: session-start
description: Chief of Staff (CoS) workspace only. The checks to run at the top of a new CoS session, before answering anything big - live runs, owed work, left-over panes, missing index lines, work you did not see, and the inbox.
---

# Session start

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this at the top of a new session, before you answer anything big. It is
one pass and three lines of output. It exists because a crash, a closed laptop,
or a new session hides work that is still open.

## The checks

If the hook context starts with `WARNING: cos.json`, tell the principal
first and help them fix `cos.json`. Until then the hooks run with default
settings.

### 1. Live runs

A run that was cut in the middle leaves its block behind.

```bash
grep -l '## Current run' memory/projects/*.md
```

For each hit, read the block. It holds the goal, the acceptance command, the
round number, and a `Node` line with the agent name and pane id. When the
`Node` line names an agent, check that agent first:

```bash
herdr agent get <name>
```

`working` -> say so and leave it. `done`, `idle`, or `blocked` -> read it and
run the next node. Gone (the pane died) -> the run needs restarting from that
node.

A `## Current run` block whose `Started:` time is older than the last log
line is a dead run. Either pick the run back up, or ask the principal to drop
it.

### 2. Owed work

`memory/index.md` is already in your context. For every project with state
`active`, open its file and read two things: `## Open decisions`, and the top
entry of `## Log`. Work that is owed is written there, in words like "still
owed", "open item", or a question waiting on the principal.

### 3. Left-over panes and agents

Only when you are inside Herdr (`test "${HERDR_ENV:-}" = 1`):

```bash
herdr agent list
herdr pane list --workspace "$HERDR_WORKSPACE_ID"
```

An agent is left over from an old session when no `## Current run` block
names it or its pane (the `Node` and `Panes` lines). A live lead's own helpers
are not left over: the lead started them, and it closes them. Close only a
pane that a `Panes` line says you opened. Never close a pane you did not
create, and never run `herdr server stop`.

### 4. Missing index lines

```bash
ls memory/projects/*.md
```

Every file except `_template.md` needs one line in `memory/index.md`. A missing
line means the last session did not finish hard rule 3 in `CLAUDE.md`.

### 5. Work you did not see

**The SessionStart hook already did this one.** The `cos` plugin lists the
folders with Claude Code sessions in the last 7 days, from every profile in
`cos.json`, so that list is in your context before you read this page. It
leaves out this workspace itself. Each row ends with the folder path, already
quoted for the shell, which the catch-up script takes as it is. Run the command yourself only when you need a
wider window:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/catch-up.py" --list --since <YYYY-MM-DD>
```

Three things matter in that list:

- a project you own with sessions **newer** than its last log line — your notes
  are behind, offer to catch up (the `cos:catch-up` skill)
- a folder with many sessions and **no file** in `memory/projects/` — ask the
  principal if you should own it
- a row from the `unknown` profile — that work ran on an account that is not in
  `cos.json`; say which folder

### 6. The inbox

The plugin's SessionEnd hook writes one line into `memory/inbox.jsonl` at the
end of every session in this workspace that had new prompts. The SessionStart
hook tells you how many are waiting. Each line holds the first new prompt and
the prompts that look like a correction — the places where the principal told
you that you went the wrong way.

Move the inbox aside before you read it, so a session that ends while you work
does not lose its line. If a past session stopped halfway,
`memory/inbox.reading.jsonl` is already there; these commands add the new
lines to it and never overwrite it. Then read it, one record per line:

```bash
if [ -f memory/inbox.jsonl ]; then
  mv memory/inbox.jsonl memory/inbox.new.jsonl &&
  cat memory/inbox.new.jsonl >> memory/inbox.reading.jsonl &&
  rm memory/inbox.new.jsonl
fi
cat memory/inbox.reading.jsonl
```

Act on each line:

| The record shows | You |
|---|---|
| `corrections` is empty, few prompts | nothing to learn, drop it |
| A correction about how you run agents or a tool | add a lesson to `memory/lessons.md` |
| A correction about a project, or a new convention | add it to `memory/projects/<slug>.md` |
| A correction about how you speak or work | add a standing preference to `identity.md` |
| `profile` is `unknown` | that session ran on an account not in `cos.json`, say so |

A correction word list only guesses. The English words are built in; words in
the principal's own language go in `cos.json` under `correction_words`. Read the
line before you trust the mark.

Two rules for what you write:

1. **Write conclusions, not prompt lines.** One line that says the rule beats
   a copied prompt.
2. **Never copy a secret.** A prompt can hold a token, a key, or a URL with a
   password. Write the lesson without it.

When every line is handled, delete the copy:

```bash
rm memory/inbox.reading.jsonl
```

## What you say

Three lines, at most. Outcome first. Example:

```
2 projects active. web-app waits on the principal's call on the login flow.
api still owes a load test for the new endpoint.
mobile-client has 11 sessions and no file here. Should I own it?
```

If everything is clean, say it in one line and stop. Do not print the checks.

## What this is not

This is not a plan and not a report. Do not write a file, except the notes and
the inbox steps from check 6. Do not start an agent during session start. You
are only reading state and handing the principal the choice.
