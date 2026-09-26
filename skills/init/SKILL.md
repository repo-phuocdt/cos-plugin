---
name: init
description: Create a new Chief of Staff (CoS) workspace in the current folder. Asks for the agent name, the chat language, how to address the principal, the Claude profiles, and the Herdr runtimes, then writes CLAUDE.md, identity.md, cos.json, and memory/.
argument-hint: "[name=<agent name>] [language=<chat language>] [address=<how to address you>] [profiles=<name=dir,...>] [runtimes=<kind,...>]"
disable-model-invocation: true
---

# Create a Chief of Staff workspace

Arguments given: $ARGUMENTS

Follow these steps in order. Until step 4, talk to the user in the language
they write in.

## 1. Check the folder

Run `ls -A` in the current folder.

- `cos.json` is there and holds `"cos_workspace"` → this is already a
  workspace. Do not ask the questions again. Read the answers from `cos.json`
  and run step 3 with them: the script only adds the files that are missing.
  Then say which files were added and stop.
- `cos.json` is there without `"cos_workspace"` → it belongs to some other
  tool. Say so and stop.
- The folder holds other work (for example `.git`, `package.json`, or source
  files) → a workspace should be its own folder. Ask the user to confirm
  before you go on.
- Empty, or only `.claude/` → go on.

## 2. Collect the answers

Take each answer from the arguments when it is there (`key=value`, quote a
value with spaces). Ask only for the ones that are missing, with
`AskUserQuestion`, and offer the default as the first option. That tool takes
at most four questions per call, so ask in two calls:

1. `name`, `language`, `address`
2. `profiles`, `runtimes`

| Key | Question | Default |
|---|---|---|
| `name` | What should your Chief of Staff be called? | `Chief of Staff` |
| `language` | Which language should it chat in? | `English` |
| `address` | How should it address you? (a name, a title, or plain "you") | `you` |
| `profiles` | Which Claude profiles may it start agents on? Each is `name=<CLAUDE_CONFIG_DIR>`, comma-separated. | one profile, `default`, on the current config dir |
| `runtimes` | Which Herdr agent kinds may it start? (`claude`, `codex`, `gemini`, `opencode`, ...) | `claude` |

If you cannot ask (a non-interactive run), or the user says "defaults", use
the default for every missing answer. Never invent other values.

## 3. Write the workspace

Run the plugin's script once. Pass one `--profile` per profile and one
`--runtime` per runtime. Leave out a flag to use its default. Put every value
in single quotes; write a single quote inside a value as `'\''`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init-workspace.py" --dir "$PWD" \
  --name '<name>' --language '<language>' --address '<address>' \
  --profile '<name>=<config dir>' --runtime '<kind>'
```

The script never overwrites a file. It prints each file as `created`, `kept`,
or `updated`. Show that list to the user as it is. If it prints `error:`, show
the error, help the user fix it, and run the same command again.

## 4. Hand over

From here on, speak in the chosen language. Tell the user, in three short lines:

1. Start a new Claude Code session in this folder, inside Herdr
   (`HERDR_ENV=1`), so `CLAUDE.md`, `identity.md`, and the hooks load.
2. Edit `identity.md` to add standing preferences, and `cos.json` to change
   profiles, runtimes, or `correction_words` (words in their language that
   mean "no, that is wrong").
3. The first thing to say in the new session is a project to own or an idea to
   frame.
