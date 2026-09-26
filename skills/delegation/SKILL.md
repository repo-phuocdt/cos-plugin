---
name: delegation
description: Chief of Staff (CoS) workspace only. How to start, prompt, check, and close other agents through Herdr, and the task-file shape for a delegate. Load before you touch any other agent.
---

# Delegation

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this before you touch another agent. It is short on purpose.

## The one rule

You start other agents **only through Herdr**. Not through the built-in
sub-agent system. `/cos:init` writes `.claude/settings.json` in this workspace
with a deny rule for the `Task` and `Agent` tools, so a sub-agent call fails by
design.

Why: a Herdr agent is a **main agent**. It has its own full context window, its
own model, and its own session. A sub-agent is a short-lived helper inside your
own context. You want peers you can talk to over time, not short-lived
helpers you throw away.

The rule is about who does the work, not only about which tool starts an
agent. A read, a grep, a `cat`, or a test run inside another repo is the
agent's job too. You take the job, frame it, hand it over, and report the
result back. `identity.md` holds the short list of things you still do
yourself; nothing outside that list belongs to you.

## Before you start

Read `memory/lessons.md`. It holds what went wrong with agents before, and it
is short. If a `herdr` skill is installed, load it for the exact command
syntax; if not, use `herdr --help`. Check you are inside Herdr:

```bash
test "${HERDR_ENV:-}" = 1
```

If that fails, you are not in a Herdr pane. Tell the principal to start you
inside `herdr` and stop. Do not fall back to sub-agents.

## The loop

This is the loop for **one** agent. For the full cycle with a verify gate and
a stop rule, load the `cos:loop` skill.

1. **Frame.** Write the goal, the constraints, the non-goals, and the
   acceptance test in one short block. If you cannot write the acceptance test,
   you are not ready to delegate. The one exception is a plan-only run (gate 1
   in the `cos:loop` skill).
2. **Pick a runtime and a profile.** See the `cos:model-routing` skill. The
   profile is a `config_dir` from `cos.json`.
3. **Open a pane** in the project's directory, without stealing focus:

   ```bash
   herdr pane split --current --direction right --cwd <project-path> --no-focus \
     --env CLAUDE_CONFIG_DIR=<profile config_dir>
   ```

   Always set the profile on the pane. Use the full path from `cos.json`, not
   `~`: a shell does not always expand `~` there. A pane outlives one agent,
   and the next Claude agent that lands there takes that account. Read the new pane id from
   `.result.pane.pane_id`.
4. **Start the agent** with a name that says its job:

   ```bash
   herdr agent start reviewer --kind claude --pane <pane-id> -- --effort <level>
   ```

   Pick `<level>` from step 3b in the `cos:model-routing` skill.

5. **Prompt it, then hand the turn back.** Never use `--wait`. Send the
   prompt, check it landed, and stop:

   ```bash
   herdr agent prompt reviewer "<the framed task>"
   herdr agent get reviewer      # expect agent_status: working
   ```

   Then tell the principal three things in one line — the agent name, the pane
   id, and what it is doing — and end your turn. The principal can now give you
   new work. See "Never block the session" below.

6. **Check back later**, when the principal asks or at the top of your next
   turn:

   ```bash
   herdr agent get reviewer      # working | blocked | done
   herdr agent read reviewer --source recent-unwrapped --lines 150
   ```

7. **Decide.** Accept, send a follow-up prompt, or bring it to the principal.
8. **Close the pane** when the job is done, so the screen and the machine stay
   clean:

   ```bash
   herdr pane close <pane-id>
   ```

9. **Write it down** in the project's file under `memory/projects/`. If the
   agent itself surprised you — not the code — add a lesson to
   `memory/lessons.md` as well.

## Before a maker starts in a worktree

Only the principal asks for a worktree. By default the maker works in the
project directory on a branch. See gate 7 in the `cos:loop` skill. This section
applies when they did ask.

A worktree does not carry untracked files. If the repo keeps `.claude/`,
`CLAUDE.md`, or a plans folder untracked, the maker starts with none of the
rules it is told to follow. When the target is a fresh worktree, make this the
first step in the task file, before any other work:

```bash
git status --ignored --short   # in the main repo
```

The agent copies any untracked rules file into the worktree. That is the
agent's job, not yours (hard rule 1 in `CLAUDE.md`).

## Never block the session

Your session is where the principal talks to you. A `--wait` call blocks it
for as long as the agent runs, so the principal cannot give you the next job.
That is a bad trade: the agent has its own pane and its own context, and it
keeps working whether you watch it or not.

Rules:

- Do not pass `--wait` to `herdr agent prompt`. Do not use `herdr agent wait`
  to sit on a long run.
- After you prompt, run `herdr agent get <name>` once. `working` means it
  landed. `idle` a few seconds later means it did not — fix that now, it is
  cheap.
- Write the agent name and its pane id into `## Current run` in the project
  file, so a new session can pick the run up.
- Then answer the principal in one line and stop.

### Get woken up, do not sit still

Handing the turn back has one cost: nothing tells you the agent finished. The
principal should not have to ask "is it done yet?".

So right after the `agent get` check, start one **background** wait:

```bash
herdr agent wait maker --until done --timeout 3600000   # run it in the background
```

Run it with the harness's background-run option, not with `&`. The command
sits outside your turn, and the harness calls you back when it exits. Then you
read the agent and run the next node.

Four rules keep this honest:

- One background wait per agent. Two waits on the same name is noise.
- Always give it a `--timeout`. A wait with no end becomes a process nobody
  stops.
- The wait is a signal, not proof. When it returns, still run `herdr agent get`
  and read the output. `done` can also mean the agent stopped to ask something.
- **A failed wait is not a finished job.** Exit code 1 with
  `agent_not_running` means the agent is gone — the pane was closed, or it
  crashed. Its work is lost. Run `herdr agent list`, say so to the principal,
  and ask before starting the job again. Never read a failed wait as success.

When you come back, read the agent. Three states:

| State | You |
|---|---|
| `working` | say so, in one line, and move on |
| `blocked` | read its output, answer it, or bring the question to the principal |
| `done` | read the result and run the `decide` node in the `cos:loop` skill |

**One exception** to the no-`--wait` rule: a job you expect to end in
seconds, like a scout that answers five lines. Even then, cap it —
`--wait --timeout 120000` — and never on a maker or a verifier.

## Parallel work

You may run several agents at once. Only when each one owns different files.
Never let two agents edit the same file, the same migration chain, or the same
shared config.

Give every agent a name you can address later: `reviewer`, `api-impl`,
`docs`, `scout`. Names must match `[a-z][a-z0-9_-]{0,31}` and be unique.

## Prompt shape for a delegate

Keep it in this order. It is short and it survives a fresh context.

```
Goal: <one sentence>
Repo/path: <absolute path>
Read first: <2-5 exact files>
Use skill: <one domain skill the agent has, or "none"> — invoke it before you plan or edit
May change: <files or dirs>
Must not change: <files, public contracts>
Acceptance: <a command that must pass, or a checkable result>
Report: end with Status: DONE | BLOCKED | NEEDS_CONTEXT + 2 lines summary
```

You pick the skill on the `Use skill:` line, not the agent. Name one skill that
carries reference for the job's stack (for example a frontend or database
skill), so the agent has the stack conventions loaded before it names a file.

Pick a **domain** skill only — one that carries reference material. Never name
a workflow skill that owns its own steps and stop points (a "cook", "ship", or
"vibe" style skill). Those fight the gates in the `cos:loop` skill.

`none` is a real answer. A config, docs, or one-line change has no domain, and
loading a skill for it only adds noise.

## Send the task as a file, not as a long prompt

A long prompt with newlines does not survive an agent TUI. Each newline can act
as "send", so the task arrives cut into pieces, or does not arrive at all. Herdr
still answers `agent_prompted`, so the call looks fine.

Write the block above to a file inside the agent's working directory, then send
one short line. The task file is a hand-off file (see `identity.md`). Before
you write it, add the hand-off file names to the repo's `.git/info/exclude`,
one per line, so no agent's `git add -A` can commit them:

```bash
printf '%s\n' .loop-task.md .lead-task.md .lead-report.md >> <repo>/.git/info/exclude
```

Skip a name that is already there. Also add the line `Do not commit this
file.` to the task file, and delete the file when the run ends.

```bash
herdr agent prompt maker "Read the file .loop-task.md in this directory and do exactly what it says."
```

Then check that it landed. Do not trust the JSON:

```bash
herdr agent get maker        # expect agent_status: working
herdr agent read maker --source visible --lines 20
```

If the status is still `idle` a few seconds later, the prompt did not land.

## When an agent gets blocked

`herdr agent wait <name> --until blocked` tells you it needs input. Read its
output, then:

- The answer is in your notes or the vision → answer it yourself, as the
  principal.
- The answer is a real product, cost, or risk decision → ask the principal,
  then relay the answer.

Never guess a decision that is expensive to undo.

## Cleanup

Close panes you opened. Do not close panes, tabs, or workspaces you did not
create. Never run `herdr server stop`.
