---
name: lead-agent
description: Chief of Staff (CoS) workspace only. Hand a whole job (plan, build, verify) to one lead agent that starts its own helpers, with the brief template and how to check its report. Load before you delegate anything bigger than one prompt.
---

# The lead agent

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this when you give out a job that is bigger than one prompt.

The `cos:loop` skill has you drive every node yourself: you open the planner
pane, then the maker pane, then the verifier pane. That works, but it keeps you
busy for the whole run, and the principal wants you free to talk.

So there is a second shape. You hand the whole job to **one** agent, called the
**lead**. The lead does the work and starts its own helpers. You go back to the
principal after one prompt.

```
principal -> you -> lead -> (maker, verifier, scout it starts itself)
                      |
                      +-> report -> you -> principal
```

## When to use which shape

| Job | Shape |
|---|---|
| one file, one clear fix, read-only check | drive it yourself, the `cos:loop` skill |
| a feature, a ticket, anything with plan + build + verify | give it to a lead |
| the principal wants to keep talking to you while it runs | give it to a lead |

The lead shape costs one more agent. Do not pay that for a two-minute job.

## What you still own

The lead never takes these from you:

1. The frame. Goal, constraints, non-goals, acceptance list — you write them.
2. The gates. They go into the lead's brief as rules it must obey, not as
   advice.
3. The decision after the report. `PASS` is a claim until you have read the
   output.
4. The PR and the notes. The lead stops at a committed branch; you open the PR
   and write `memory/projects/<slug>.md` (see `identity.md`).
5. Anything that touches a remote, a secret, or `main`.

## The brief

Write it to `.lead-task.md` in the repo, then send one short line pointing at
it. Same reason as in the `cos:delegation` skill: a long prompt does not
survive an agent TUI.

```markdown
# Lead task

You are the lead on this job. Do the work, and start your own helper agents
when that is faster. Report back to me at the end.

Goal: <one sentence>
Repo/path: <absolute path>
Read first: <2-5 exact files>
Use skill: <one domain skill, or "none"> — invoke it before you plan or edit
May change: <files or dirs>
Must not change: <files, public contracts>
Acceptance (frozen — do not add to this list):
  1. <command that must pass>
  2. <...>

## Rules you must obey

- Work in this directory on a new branch. No worktree.
- Plan before you edit. Say which files you will change and why.
- The agent that writes the code never grades it. Start a second agent to
  verify.
- The verifier shows raw command output. It also breaks the behavior on
  purpose and shows the same command going red. No red proof, no PASS.
- Review the diff with a code review skill before you call it done.
- Two rounds of fixing at most. Then stop and report the failure.
- Stop at a committed branch. Do not push, do not open a PR, do not merge,
  do not touch main, never commit a secret.
- Start each helper with a task file named `.<helper>-task.md` and the
  one-line prompt `Read the file .<helper>-task.md in this directory and do
  exactly what it says.` Never commit any `.*-task.md` file or
  `.lead-report.md`.
- Every helper pane uses the same Claude account as you:
  <`--env CLAUDE_CONFIG_DIR=<config_dir>` on every `herdr pane split` |
  no `--env` on any `herdr pane split` (default profile)>. Never start a
  helper on another account.
- At most <N> helper agents alive at once. Close every pane you open.
- If you stop to ask a question, write it in `.lead-report.md` with the exact
  question, the answer you got, who answered, and the time. "The user
  confirmed" with no question text is not enough.

## How to report

Write your full report to `.lead-report.md` in this directory, then say only:
"Report written to .lead-report.md" plus your Status line.

The report holds: what changed and why, the branch name, the raw output of
every acceptance check, the red proof, what the code review found, and any
open question.

Report: end with Status: DONE | BLOCKED | NEEDS_CONTEXT + 2 lines summary
```

`<N>` is 2 unless the job clearly splits into parts that touch different files.

Fill in the account rule with the profile you give the lead itself, and keep
only one of the two choices: the `--env` form with the profile's full
`config_dir` for a named profile, or "no `--env`" for the `default` profile.
A helper pane that the lead opens without `--env` takes Herdr's own
environment, so without this rule a lead on a named profile would start its
helpers on another account.
A lead with no cap starts an agent per idea and uses up the account's session
limit.

The report goes to a file, not to the pane, because a long answer scrolls off
the agent's screen and cannot be read back.

## Your side, start to end

Pick the profile from `cos.json` first (the `cos:model-routing` skill).

```bash
# 1. brief (you write .lead-task.md into the repo)
# 2. pane + agent (step 3 of the cos:delegation skill); use ONE of the two
#    pane lines, by profile
herdr pane split --current --direction right --cwd <repo> --no-focus    # default profile
herdr pane split --current --direction right --cwd <repo> --no-focus --env CLAUDE_CONFIG_DIR=<config_dir>    # named profile
herdr agent start lead --kind claude --pane <pane-id> -- --effort xhigh

# 3. prompt, no --wait
herdr agent prompt lead "Read .lead-task.md in this directory and do exactly what it says."
herdr agent get lead            # expect working

# 4. background wait — this is what wakes you up
herdr agent wait lead --until done --until blocked --until idle --timeout 3600000   # run in background
```

Then write the `Node` line into `## Current run` and give the turn back. One
line to the principal: the agent name, the pane, and what it is doing.

When the wait wakes you (the lead is `done`, `blocked`, or `idle`, or the
wait failed):

1. `herdr agent get lead` — decide from the state it shows now: `working`
   (start a new background wait), `done` or `idle` (go on), `blocked`, or
   gone.
2. Read `.lead-report.md` in the repo.
3. Check the evidence, do not trust the verdict. No raw output, or no red
   proof, is a `FAIL` however green the summary looks.
4. `blocked` -> read the question. Answer it from the notes as the principal,
   or bring a real decision to the principal.
5. `PASS` -> ask the principal about the push (loop gate 5), open the PR
   yourself after a yes, update the project file, delete
   `.lead-task.md` and `.lead-report.md`, close the pane.
6. `FAIL` after its 2 rounds -> close the pane and bring the findings to the
   principal. Do not start a fresh lead on the same frame without changing
   something.

## When the lead needs a decision

A lead that hits a real call — a major version bump, a schema change, two valid
designs — stops and asks. Its pane is on the principal's screen, so the
principal often answers it there and then. That is fine and it is fast. What is
not fine is you learning about it later, or not at all.

So the brief must say:

```markdown
- If you stop to ask a question, write it in `.lead-report.md` with: the exact
  question, the answer you got, who answered, and the time. "The user
  confirmed" with no question text is not enough.
```

And on your side: when a report says the principal approved something, read the
pane before you believe it. `herdr agent read <name> --source recent-unwrapped`
shows the real question and the real answer. A report alone cannot prove that
the principal really made the call.

## What breaks first

- **A lead that grades itself.** It runs the tests, sees green, and skips the
  verifier because it is sure. Check the report for a second agent name and a
  red proof. No second name, no PASS.
- **A lead that starts too many helpers.** Read `herdr agent list` when it
  reports. More
  agents alive than the cap means the next brief must state the cap more
  clearly.
- **A silent lead.** The background wait returns and the report file is not
  there. Read the pane, then ask the lead for the file. Do not re-run the job.
- **A lead that pushed.** The rules say stop at a branch. If it pushed anyway,
  tell the principal at once — that is theirs to undo, not yours.
