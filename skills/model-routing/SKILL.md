---
name: model-routing
description: Chief of Staff (CoS) workspace only. Which runtime, Claude profile, model, and effort level to use for a delegated job, based on cos.json and two yes/no questions. Load when you are about to delegate.
---

# Model routing

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Which runtime you hand a job to. Read only when you are about to delegate.

## What you may use

`cos.json` in this workspace holds the principal's choices. `/cos:init` wrote
it; the principal can edit it at any time.

- `runtimes` — the Herdr agent kinds you may start (`--kind claude`,
  `--kind codex`, ...). A kind that is not in the list is off. If a job seems
  to need one, say so and let the principal decide.
- `profiles` — the Claude accounts you may start agents on. Each has a `name`
  and a `config_dir`. A profile is picked with the `CLAUDE_CONFIG_DIR`
  environment variable on the pane. The `default` profile has
  `"config_dir": null`: its panes get no `CLAUDE_CONFIG_DIR`, so they use the
  normal login in `~/.claude`.

`claude` is the default runtime, and the only one for risky work unless the
principal says otherwise.

## Pick the profile first

Your own session already runs under one profile. That does **not** tell you
which one a new agent should use.

- One profile in `cos.json` -> use it.
- The project file names a `Profile:` -> use it.
- Otherwise -> **ask the principal which profile before you start any Claude
  agent.** Work paid by one account must not run on another. This is not a
  routine call you may make yourself.

Set it on the pane, then start the agent in that pane. For a profile with a
`config_dir`, pass the full path from `cos.json` (not `~`, which a shell does
not always expand there). For the `default` profile, use the command with no
`--env`: setting the variable, even to `~/.claude`, makes Claude Code look for
another saved login. A pane without `--env` takes Herdr's own environment, so
start Herdr from a shell where `CLAUDE_CONFIG_DIR` is not set.

```bash
# default profile ("config_dir": null): no --env
herdr pane split --current --direction right --cwd <project-path> --no-focus
# a profile with a config_dir: add --env with its full path
herdr pane split --current --direction right --cwd <project-path> --no-focus --env CLAUDE_CONFIG_DIR=<config_dir>
# then, in the new pane
herdr agent start maker --kind claude --pane <pane-id>
```

Put the profile on every `pane split`, even for a non-Claude pane. A pane
outlives one agent, so the next Claude agent that lands there takes that
account. Other kinds ignore the variable.

## How to pick the model

You stay on a strong model. You do not switch yourself down and do the work.
You read the ticket, judge how hard it is, then start a **separate** agent on
the model that fits. Same idea as a tech lead: the lead does not become the junior, the
lead hands the job to the right person.

Two reasons this matters. You keep your context free to judge the result when
the maker reports back. And the maker gets a clean context that holds only its
own task, not your sorting work.

### Step 1 — know the code first

Hardness is not in the ticket. "Login button does nothing" can be a CSS z-index
fix or a broken token refresh. If you judge from the ticket text alone, you
are guessing.

So before you pick a model:

- Read `memory/projects/<slug>.md`. If you have worked in this area before,
  the notes already tell you what you need. Skip to step 2.
- If you have not, start a cheap `scout` agent on a small model. Give it the
  ticket and the repo path. Ask for exactly five lines back:

```
Files likely touched: <list>
Tests covering that area: yes / no / partial
Touches public contract, schema, auth, or money: yes / no
Cause is proven: yes / no / guess
Confidence: high / low
```

Close the scout pane as soon as it answers.

A strong model with no knowledge of the repo still hands out the wrong job. It
just sounds more sure while doing it. The notes are what fix this over time, so
step 9 of the `cos:delegation` loop is not paperwork — it is what makes the
next ticket cheap.

### Step 2 — two yes/no questions

Do not score 1 to 5. You would score it differently each session. Two yes/no
questions stay stable:

1. **Can you write a concrete acceptance test?** The `cos:delegation` skill
   already makes you do this. If you cannot, the ticket is still unclear.
2. **Is being wrong expensive?** Yes when scout says it touches a public
   contract, schema, auth, or money — or when there are no tests. No tests
   means no safety net.

| Acceptance test | Wrong is expensive | Lane |
|---|---|---|
| you can write it | no | small model, go straight to work |
| you can write it | yes | strong model, plus a verifier agent |
| you cannot write it | no | strong model to **plan only**, then a small model to code it (the one exception to gate 1 in `cos:loop`) |
| you cannot write it | yes | stop and ask the principal |

The last row is the important one. Unclear **and** expensive is not a model
problem. It is a missing decision. Spending a strong model there only buys a
confident guess.

"Small model" and "strong model" are roles. For a Claude agent, a small model
is an alias like `sonnet` or `haiku`, and a strong model is your best one, like
`opus`. For another runtime in `runtimes`, use that tool's own cheap and strong
models. A runtime that bills a third party never gets the strong-model rows
unless the principal said so for that repo.

### Step 3 — start the maker on that model

Pick the profile first (above), then:

```bash
# default profile ("config_dir": null): no --env
herdr pane split --current --direction right --cwd <project-path> --no-focus
# a profile with a config_dir: add --env with its full path
herdr pane split --current --direction right --cwd <project-path> --no-focus --env CLAUDE_CONFIG_DIR=<config_dir>
# then, in the new pane
herdr agent start maker --kind claude --pane <pane-id> -- --model sonnet --effort medium
```

Anything after `--` goes straight to the `claude` binary. Keep the profile on
the pane env and the model on the agent args: one pane holds one profile, but a
maker and a verifier in different panes can run different models.

### Step 3b — pick the effort level

Every Claude agent gets `--effort <level>`. Effort sets how hard the agent
thinks on each turn. Model and effort are two separate knobs: model is *who*
does the job, effort is *how hard* they try. Pick it from the same answers as
step 2. Never leave it out — then the agent silently uses its default.

| Effort | Use it for |
|---|---|
| `low` | template jobs with a fixed answer shape: create a branch, commit, open a PR, read a ticket, the scout in step 1 |
| `medium` | small model, straight to work: clear ticket, tests exist, wrong is cheap; mechanical edits |
| `high` | the default for real code: a maker that codes a plan someone else wrote, or a bug whose cause is proven |
| `xhigh` | wrong is expensive (contract, schema, auth, money, no tests); a plan-only run; a lead agent on a multi-phase job; the verifier |
| `max` | only the second retry after a round failed because the job was too hard, or a bug whose cause is still a guess after scout |

Rules:

- Start one level lower when unsure. Step 4 still applies: move up on the
  retry, never mid-run.
- A failed round moves **effort** up first when the model already fits. Move
  the **model** up when the agent missed things a stronger model would see.
- `max` is rare. It is slow and costs the most. If a job needs it on the first
  try, it is probably the "stop and ask the principal" row instead.
- A runtime with no effort flag skips this step.

### Step 4 — expect to guess wrong

The first guess does not need to be right. It needs to be cheap, and when it
fails you must see it fail. Start at the cheapest sane lane. When the first verify round fails and
the cause looks like the model was too weak for the job, spend the **second**
retry on a stronger model instead of the same one.

Moving up a lane spends a retry. It does not buy an extra one. The budget in
the `cos:loop` skill is still 2 rounds, then stop and bring it to the
principal.

Signals that the lane was wrong, not the code:

- the maker asks a second question — the ticket is less clear than you thought,
  so this is the "plan first" row, not a stronger maker
- the diff touches more than twice the files scout expected — this is a misread
  task, so **stop**. Do not move up, do not retry.

To move up a lane: close the pane, start a fresh maker on a stronger model with
the same task file. Never change model mid-run.

## Cost rule

You are the reasoning layer. Other agents are the execution layer. If you are
about to do a large mechanical task yourself — read 20 files, run a big
refactor, work through a whole test suite — stop and delegate it. Your context is the
limited thing; keep it for the decisions.

## Per-project override

If a project's file in `memory/projects/` names a preferred runtime or a
profile, that wins over this page.
