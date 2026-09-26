---
name: intake
description: Chief of Staff (CoS) workspace only. Turn a rough idea from the principal into a five-line frame (outcome, constraints, non-goals, acceptance, project) before any work is delegated. Load before you frame any work.
---

# Intake

Only for a Chief of Staff workspace (a folder with `cos.json`). In any other
folder, stop here.

Read this when the principal hands you a rough idea. It ends when you have a
frame you can delegate. The `cos:loop` skill picks up from there.

## What you must end with

Five lines. Not more.

```
Outcome:     <one sentence, in the principal's words>
Constraints: <what the change must respect>
Non-goals:   <what this change is not>
Acceptance:  <a command that must pass, or a checkable result>
Project:     <slug in memory/projects/, or "new">
```

If you cannot fill all five, you are still in intake. Do not open a pane.

## Order of work

1. **Read the project file first.** Most new ideas are the next step of a
   project you already own. Its Goal, Rules, and Open decisions answer half the
   questions before you ask any.
2. **Look, do not ask.** Anything that sits in the repo, the git log, or your
   own notes is not a question. Read your notes, or send a scout agent (step 1
   in the `cos:model-routing` skill).
3. **Draft the five lines yourself.** A draft you show is faster than a
   question you ask. The principal fixes a wrong line in three words.
4. **Ask only what is left.** See the table below. One message, at most three
   questions.
5. **Read the five lines back and get one yes.** Then start the loop.

## What you decide, what you ask

| The question is about | You |
|---|---|
| File layout, naming, branch name, which test to run | decide |
| A library the repo already uses | decide, follow the repo |
| A small refactor inside the scope you were given | decide |
| Anything the repo or your notes can answer | look it up |
| Product behavior the user will see | ask |
| Money, auth, schema shape, a public contract | ask |
| Deadline, priority against another project | ask |
| Two readings of the ask that give very different work | ask |

Rule of thumb: ask when a wrong guess is expensive to undo. Otherwise decide,
write down what you decided, and move.

## The ask is the scope

Write down only what was asked. Do not add a nice extra, a cleanup next door,
or a test suite nobody wanted. If you see real work outside the ask, put it in
`## Open decisions` in the project file and tell the principal in one line.

## When to stop instead of start

Stop and bring it back to the principal when:

- You cannot write the acceptance line. That is gate 1 in the `cos:loop`
  skill. An unclear ask is not a model problem. (A plan-only run is the one
  exception; see gate 1.)
- The ask is unclear **and** being wrong is expensive. See the last row of the
  lane table in the `cos:model-routing` skill.
- The ask needs a decision only the principal can make, and the notes do not
  hold it.

Say which of the three it is. Do not open the loop and hope.

## Where the frame goes

- Into the project file, as the `## Current run` block (the `cos:loop` skill).
- Into the task file the maker reads (the `cos:delegation` skill).
- If the project is new: create `memory/projects/<slug>.md` from
  `memory/projects/_template.md` and add one line to `memory/index.md` first.
