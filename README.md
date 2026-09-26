# cos — a Chief of Staff plugin for Claude Code

This plugin gives you your own **Chief of Staff** (CoS). The CoS is a Claude
Code agent that lives in one folder, the *workspace*. It does not write code.
It takes your rough ideas, turns them into clear jobs, hands each job to other
coding agents, checks their work, and keeps notes so you never repeat context.

What you get:

| Part | What it does |
|---|---|
| Persona | `identity.md` and `CLAUDE.md` in your workspace: who the CoS is, how it speaks to you, and its hard rules. |
| Memory | `memory/index.md` plus one file per project in `memory/projects/`, and `memory/lessons.md` for lessons about agents. |
| Intake | The `cos:intake` skill turns a rough idea into a five-line frame: outcome, constraints, non-goals, acceptance, project. |
| Delegation | The `cos:delegation`, `cos:loop`, `cos:lead-agent`, and `cos:model-routing` skills: how the CoS starts and checks other agents through Herdr. |
| Catch-up | The `cos:catch-up` skill and a script that read your Claude Code transcripts, so the CoS learns about work you did without it. |
| Session hooks | At session start: a list of recent sessions and the inbox count. At session end: one record added to `memory/inbox.jsonl`. |

## What you need

- **Claude Code**, with plugin support (`claude plugin --help` works).
- **Python 3** (standard library only; nothing to install).
- **Herdr**, a terminal multiplexer for coding agents (one window that runs
  many terminals, called panes). The CoS starts every
  other agent in a Herdr pane. Run the CoS inside Herdr, so `HERDR_ENV=1` is
  set. Outside Herdr, the CoS stops and asks you to start it inside Herdr.
- **git**, for the repos the agents work in.

## Install

The plugin folder is also a local marketplace (`.claude-plugin/marketplace.json`).

1. Get this folder on your machine (clone or copy it). Below, it is
   `/path/to/cos-plugin`.
2. Add it as a marketplace:

   ```bash
   claude plugin marketplace add /path/to/cos-plugin
   ```

3. Make an empty folder for your workspace, and install the plugin there:

   ```bash
   mkdir ~/cos && cd ~/cos
   claude plugin install cos@cos-plugin --scope project
   ```

   `--scope project` turns the plugin on in this folder only. You can also
   install it for your user (the default scope). That is safe too: the hooks
   do nothing outside a CoS workspace, and the guide skills say to stop there.

4. Check it:

   ```bash
   claude plugin list
   ```

## First run

1. Start Herdr, open a pane in your workspace folder, and start Claude Code:

   ```bash
   cd ~/cos
   claude
   ```

2. Run the init command:

   ```
   /cos:init
   ```

   It asks five things, in two rounds. Each one has a default:

   | Question | Default |
   |---|---|
   | The agent's name | `Chief of Staff` |
   | The chat language | `English` |
   | How it addresses you | `you` |
   | Claude profiles it may use (`name=<CLAUDE_CONFIG_DIR>`) | one profile, `default`, on your current config dir |
   | Herdr runtimes it may start (`claude`, `codex`, ...) | `claude` |

   You can also pass the answers, and skip the questions:

   ```
   /cos:init name="Ada" language=English address=Sam profiles="work=/home/me/.claude-work,home=/home/me/.claude-home" runtimes=claude,codex
   ```

3. It creates these files and never overwrites one that exists. If a
   `.gitignore` is already there, it only adds the missing inbox lines:

   ```
   ~/cos
   ├── CLAUDE.md                  # loads identity.md and memory/index.md
   ├── identity.md                # the persona; edit it to add preferences
   ├── cos.json                   # name, language, address, profiles, runtimes
   ├── .gitignore                 # keeps the inbox files out of git
   ├── .claude/settings.json      # turns off built-in sub-agents here
   └── memory/
       ├── index.md               # one line per project
       ├── lessons.md             # empty at start
       ├── inbox.jsonl            # written by the SessionEnd hook
       └── projects/_template.md  # copy this for each new project
   ```

4. Quit, then start a new Claude Code session in the same folder, so
   `CLAUDE.md` and the hooks load. Tell your CoS about a project it should own,
   or give it an idea to frame.

## Settings: `cos.json`

```json
{
  "cos_workspace": 1,
  "agent_name": "Chief of Staff",
  "language": "English",
  "address": "you",
  "profiles": [{ "name": "default", "config_dir": "/home/me/.claude" }],
  "runtimes": ["claude"],
  "correction_words": []
}
```

- `cos_workspace` — marks the folder as a CoS workspace. Keep it.
- `profiles` — the Claude accounts the CoS may start agents on. Each agent
  pane gets `CLAUDE_CONFIG_DIR=<config_dir>`, so use full paths (init turns
  `~` into a full path for you). With more than one profile, the
  CoS asks you which one to use. The hooks and the catch-up script read
  transcripts from these folders.
- `runtimes` — the Herdr agent kinds the CoS may start. Anything else is off.
- `correction_words` — words in your language that mean "no, that is wrong".
  English words like "no", "wrong", and "instead" are built in. The hooks use
  them to mark the prompts where you corrected an agent.

`agent_name`, `language`, and `address` are also written into `identity.md`
and `CLAUDE.md` at init. To change them later, edit those files too.

## Hooks

Both hooks first check that the session's folder is a CoS workspace: it holds
a `cos.json` written by `/cos:init` (with `"cos_workspace": 1`) and a
`memory/` folder. If not, they print nothing and write nothing. If `cos.json`
has a typo and cannot be read, the folder still counts as a workspace: the
hooks run with default settings, and SessionStart adds one warning line.

- **SessionStart** (`scripts/session-start.py`) adds to the session's context
  the folders with Claude Code sessions in the last 7 days (from every profile
  in `cos.json`, leaving out the workspace itself) and the number of records
  in `memory/inbox.jsonl`. It runs at every session start: new, resumed,
  cleared, or compacted.
- **SessionEnd** (`scripts/session-end.py`) appends one JSON line to
  `memory/inbox.jsonl`: the time, the reason, the profile, the number of human
  prompts, the first prompt, and up to six prompts that look like corrections.
  Each prompt is recorded once, even when a session is resumed: the hook
  keeps the keys of recorded prompts in `memory/.inbox-seen.json`. Nothing is
  written when there is no new human prompt. The CoS
  turns these lines into notes at the next session start, then clears the
  inbox.

To test a hook by hand, pipe a payload into it. Put your own paths in; the
transcript must hold at least one prompt. This adds a real line to the inbox:

```bash
echo '{"session_id": "abc123", "cwd": "/home/me/cos", "transcript_path": "/path/to/transcript.jsonl", "reason": "other"}' \
  | python3 /path/to/cos-plugin/scripts/session-end.py
```

Privacy: the inbox holds the first 200 characters of your prompts. It stays in
your workspace folder, and `/cos:init` adds the inbox files to `.gitignore` so
git does not pick them up by mistake.

## Skills

| Skill | Use |
|---|---|
| `/cos:init` | Create a workspace in the current folder. You run it; the model does not. |
| `cos:session-start` | The checks at the top of each session. |
| `cos:intake` | Frame a rough idea before any work starts. |
| `cos:delegation` | Start, prompt, check, and close agents through Herdr. |
| `cos:loop` | The ship-one-change loop: plan, build, verify by a second agent, stop at a PR. |
| `cos:lead-agent` | Hand a whole job to one lead agent. |
| `cos:model-routing` | Pick the runtime, profile, model, and effort. |
| `cos:catch-up` | Learn from work done without the CoS. |

A rule you write in your workspace's `identity.md` wins over these guides.

## Uninstall

```bash
claude plugin uninstall cos@cos-plugin --scope project
claude plugin marketplace remove cos-plugin
```

Your workspace files stay where they are.
