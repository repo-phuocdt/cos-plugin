---
name: loop
description: Chief of Staff (CoS) workspace only. The ship-one-change loop - nodes, gates, retry budget, run state, and where a run stops. Load before you run work end to end through other agents.
---

# The loop

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this before you run work that should finish without the principal typing
each step. The `cos:delegation` skill says how to talk to one agent. This page
says how to run the whole cycle.

The idea is simple. You do not prompt an agent. You run a loop that prompts
agents, checks their work, and stops on its own.

**Who runs the loop is a choice.** This page has you drive every node. That
fits a small, single-file job. For a real ticket, hand the whole loop to one
lead agent instead and keep your desk free — see the `cos:lead-agent` skill.
The gates below do not change; they move into the lead's brief as rules.

## The one loop we run

Name: **ship-one-change**. It ends at an open PR. A human merges.

```
frame -> plan -> implement -> verify -> decide -> [back to implement | open PR]
      -> record
```

There is only one loop here on purpose. Do not add a second loop, a second
orchestrator, or parallel makers until one of these is true: two changes touch
different files and both are urgent, or a step needs a different permission
level, or a failure in one part must not stop the other.

## Two sizes, one loop

A small fix does not need the full weight. Same loop, fewer steps. Read the
scout answer from step 1 of the `cos:model-routing` skill and ask three
questions:

1. Is the cause proven, or is the change plainly mechanical?
2. Does it stay away from public contracts, schemas, auth, money, and user
   data?
3. Do tests already cover the area?

**Three yes -> short run.** Anything else -> the full run below.

| Step | Short run | Full run |
|---|---|---|
| frame | one acceptance check | acceptance check, constraints, non-goals |
| edge-case pass | skip | yes, at plan |
| plan | one line inside the maker's first reply, no approval round | its own step, you approve before any edit |
| implement | same | same |
| verify by a second agent | **always** | **always** |
| red proof (gate 3) | **always** | **always** |
| code review of the diff | **always** | **always** |
| retry budget | 2 | 2 |
| stop at PR | **always** | **always** |

In a short run the maker still says which files it will touch and why the bug
happens **before** it edits — it just says it in the same reply, and you read
it instead of running a separate round. If that one line names files you did
not expect, stop and switch to the full run. That is the misread-task signal
from the `cos:model-routing` skill, and it costs nothing to obey here.

What a short run never cuts is the proof: a different agent, real output, and a
red check before the green one. That is what makes the result worth trusting.
Cutting planning saves time. Cutting proof only moves the cost to the PR.

## Nodes

| Node | Who runs it | What it does |
|---|---|---|
| frame | you (CoS) | Write goal, constraints, non-goals, acceptance command. |
| plan | a delegate agent | Read the code. Say which files change and how. No edits yet. |
| implement | a delegate agent | Change the code. |
| verify | a **different** delegate agent | Run the acceptance command. Judge the diff. |
| decide | you (CoS) | Pass, retry, or escalate. |
| pr | you (CoS) | Commit, then PR if the repo has a remote. Then stop. |
| record | you (CoS) | Update `memory/projects/<slug>.md`. |

Not every node needs an agent. `decide`, `pr`, and `record` are your job. Do
not spend an agent on them.

## Gates

A gate is a hard rule. It lives here, not inside a prompt.

1. **No acceptance command, no start.** If you cannot write a command that
   proves the work is done, you are not ready. Ask the principal instead.
2. **The maker never grades itself.** `verify` runs as a separate Herdr agent,
   started in a fresh pane, ideally a different `--kind`. It never reads the
   maker's chat.
3. **Verify must show output.** The verifier pastes the real command output. A
   claim of "tests pass" without output is a fail.
   Green alone proves nothing — a test can pass whether the feature works or
   not. The verifier must also break the behavior on purpose (revert the fix,
   or feed it a bad input) and show the same command turning red. No red
   check shown, no PASS.

   **Typecheck and unit tests are not enough for anything a user sees or
   does.** They prove the code compiles and the functions it calls behave in
   isolation — not that the app still opens, that a screen still renders, or
   that a click still does the thing. Code can review clean with every check
   green and still crash the moment a person runs it. So: for any change that
   touches a route, a screen, or a user-visible flow, the acceptance list is
   not complete until it includes actually starting the app and going through
   that flow — a browser tool, a screenshot, a captured console log, or (for
   a backend or CLI change with no UI) the real command run against real
   input, not a mock. Add this to the acceptance command at frame time, not as
   an afterthought at verify time.
4. **Retry budget is 2.** After 2 failed verify rounds, stop the loop and bring
   the verifier's findings to the principal. Do not try a third time.
5. **Stop before the principal's review.** The stop point depends on the repo:
   - has a remote -> push the branch and open a PR with the repo's own tool
     (`gh` for GitHub, the web UI for other hosts).
   - no remote -> commit on a branch and stop there.
   The loop never merges, never pushes to the main branch, never force pushes,
   never deletes a branch, never commits a secret. Any of these needs the
   principal to say yes first.

   **A live check the verifier cannot run is a stop, not a skip.** If gate 3's
   runtime check is blocked — no authenticated session, no seeded data, no
   working local environment — that is not a "known gap" to note in the PR
   body and ship past. It means the diff has never actually run. Stop the
   loop before the PR and tell the principal exactly what is blocked and what
   would unblock it (a test account, a seed script, a stored session). They
   either unblock it so the check can run for real, or they knowingly accept
   the risk — but that is their call to make before it ships, not something
   the loop decides for them by staying quiet. A blocker seen twice on one
   repo is an open item in `memory/projects/<slug>.md`, not a recurring
   footnote.
6. **No plan, no code.** The maker says what it will change before it changes
   it. In a full run that is its own step and you approve it. In a short run it
   is one line in its first reply. Either way, a plan that names files you did
   not expect is a misread task — fix the frame, do not wave it through.
7. **No worktree unless the principal asks for one.** The agent works in the
   project directory on a branch. Create a worktree only when the principal
   says so, in that run. Do not add one because the change looks big.
8. **The loop never blocks your session, and never goes quiet either.** After
   you prompt an agent you check it landed, start one background
   `herdr agent wait <name> --until done --timeout <ms>`, and hand the turn back
   to the principal. The run lives in `## Current run`, not in a `--wait` call.
   The background wait is what brings you back, so the principal never has to
   ask whether the agent finished. See "Never block the session" in the
   `cos:delegation` skill.

## What each agent may see

Running after another agent does not give you its context. Keep these limits.

| Agent | Gets | Never gets |
|---|---|---|
| planner | goal, constraints, non-goals, acceptance command, repo path | permission to edit a file in this step |
| maker | goal, constraints, the approved plan, acceptance command | the principal's private notes, other projects |
| verifier | goal, the frozen acceptance list, the diff or branch name | the maker's chat, the maker's own summary |

The verifier must reach its own answer. If you paste the maker's report into
the verifier, the gate is gone.

## Run state

Keep the state of a live run in the project's file under `memory/projects/`,
in a section called `## Current run`. A few lines is enough:

```markdown
## Current run
- Goal: <one sentence>
- Acceptance: <the checks, frozen when you approved the plan>
- Plan: approved — <files it will touch> | waiting
- Round: 1 of 2
- Node: implement — waiting on agent `maker` in pane `<pane-id>`
- Last verify: FAIL — <one line why>
```

The `Node` line is what makes gate 8 work. It names the step the run sits on,
the agent, and the pane, so any later turn — or a new session — can read the
agent instead of starting the work again. Update it every time you prompt an
agent or read one back.

Delete the section when the PR is open and the line is in the log. This block
is what lets you pick the loop back up after a crash or a new session.

## Steps

Every step that prompts an agent ends the same way: check the prompt landed,
write the `Node` line, tell the principal in one line, stop. The next step runs
when you come back and the agent is `done`, not while you hold the session
open.

1. **frame** — write the block from the `cos:delegation` skill. Add the
   acceptance command. Write `## Current run` into the project file.
2. **plan** — pick a runtime from the `cos:model-routing` skill. Open a pane in
   the project directory, start the agent, and ask for two things, with no
   edits yet:
   - the edge cases the ticket did not name (use an edge-case or scenario
     skill if the agent has one);
   - a plan: the files it will change, what changes in each, and how the
     acceptance command proves it.

   Turn the edge cases that matter into extra acceptance checks. You pick which
   ones count, not the agent — most of its list will be noise for a small
   ticket. The acceptance list is frozen once you approve the plan. Growing it
   after the maker starts is moving the goal, and it is how a run never ends.

   Read the plan against the frame. Three outcomes:
   - fits the frame -> write the file list into `## Current run`, go to step 3.
   - touches files you did not expect, or misses part of the goal -> fix the
     frame and ask again. This costs no retry; the code is still untouched.
   - the plan exposes a real decision (a schema change, a contract break, two
     valid designs) -> stop and ask the principal. That is not yours to call.
3. **implement** — prompt the same agent to build the approved plan. Same pane,
   same agent: it already holds the plan and the code in context. It works in
   the project directory on a branch, not in a worktree, unless the principal
   asked for one.

   One exception: when the `cos:model-routing` skill puts the ticket in the
   "strong model plans, small model codes" lane, close the planner pane and
   start a fresh maker on the small model with the plan as its task file.
4. **verify** — open a second pane. Start a second agent with a different name
   (`verifier`). Give it only the goal, the branch, and the acceptance list.
   Ask for two passes and one verdict:
   - run every acceptance check, and show the raw output;
   - review the diff with a code review skill (for example `/code-review`)
     and report what it finds.

   Verdict is `PASS` or `FAIL` plus reasons. A green run with a real review
   finding is still a `FAIL` — a check passing does not make bad code fine.
5. **decide**
   - `PASS` -> go to step 6.
   - `FAIL` and round < 2 -> send the verifier's findings back to the maker.
     Bump `Round` in the project file. Go back to step 4.
   - `FAIL` and round = 2 -> close the panes, tell the principal what failed,
     stop.
6. **pr** — commit on the branch. Push and open a PR only if the repo has a
   remote. Do not merge. Tell the principal the URL or the branch name.
7. **record** — close every pane you opened. Update the project file: add one
   log line, remove `## Current run`. Then ask one question: did an agent or a
   tool behave in a way you did not expect? If yes, add a lesson to
   `memory/lessons.md`.

## Which skills the loop uses

Use what the delegate has installed. Four kinds help, plus one domain skill
you choose per ticket:

| Node | Kind of skill | What it buys |
|---|---|---|
| scout (step 1 of `cos:model-routing`) | a scouting or code search skill | files and tests for the area, before you pick a model |
| plan | an edge-case or scenario skill | edge cases the ticket did not name, which become extra acceptance checks |
| plan and implement | one domain skill, picked by you | the stack's own conventions, before the agent names a file |
| verify | a code review skill, such as `/code-review` | a read of the diff, not just a green check |
| verify, when the ticket touches auth, money, or user data | a security review skill, such as `/security-review` | a threat pass on the same diff |

The security pass is conditional on purpose. Running it on a CSS fix wastes a
round and teaches you to skim its output.

The domain skill is the only row you choose. Name that one skill on the
`Use skill:` line of the task block in the `cos:delegation` skill. It covers
both `plan` and `implement` because a planner that does not know the stack
names the wrong files. `none` is a real answer for a config or docs ticket.

Two kinds of skill, and only one kind is barred. A **domain** skill carries
reference for a stack and has no steps of its own, so it is safe. A
**workflow** skill owns its own steps, gates, and stop point — a skill that
plans, builds, reviews, and ships in one go. Two sets of rules then fight, and
the gates on this page lose. Keep workflow skills out of this loop: this loop
is the workflow. The same goes for a skill that writes its own plan documents
or journals — your plan is a short block you approve once, and
`memory/projects/<slug>.md` is the one record.

## What breaks first

Watch for these. They are the normal ways a loop goes wrong.

- **A soft verifier.** If the verifier keeps saying PASS, it is reading the
  maker's words instead of running the command. Check gate 3.
- **Code nobody read.** The loop ships faster than you read. The code review
  in verify and the PR stop both exist for this. Do not raise the retry budget
  to skip either.
- **An acceptance list that keeps growing.** An edge-case pass will hand you
  more cases than a ticket deserves. Pick a few at plan time, then freeze the
  list. A list that grows every round is a run that never ends.
- **A loop with no end.** Every run must have a round count and a budget. If
  you cannot see the round number, the loop is not engineered.
