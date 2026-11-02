# SDD Setup — Prerequisites & One-Time Configuration

Everything you configure once per machine or per project. For the flow and
commands see [pipeline.md](pipeline.md); for the concepts see [concepts.md](concepts.md).

---

## Prerequisites

- **Python 3.7+** reachable as `python3` on your PATH — the pipeline shells out to it
  for its artifact gates and helpers (`start.py`, `plan.py`, `triage.py`, `gates.py`, plus
  inline helpers in `/sdd:mr`, `/sdd:resync`, `/sdd:implement`). Verify with `python3 --version`.
  The plugin's `SessionStart` hook (`hooks/check-python.sh`) checks for it and, if only
  `python`/`py` exist, drops a `python3` shim into `~/.claude/bin` (add that dir to your
  PATH when prompted).
- **git** and a POSIX shell (bash or zsh).
- `glab` (optional, for automatic MR creation).

---

## Install (do this as a plugin, not standalone)

Add the plugin from whatever source you host it on — **the plugin does not depend on
any particular host.** A marketplace can be a git URL on *any* host, or a plain local
path:

```text
# any git host (GitHub, GitLab, self-hosted, …)
/plugin marketplace add <git-url-of-this-repo>

# or straight from a local clone — no remote at all
/plugin marketplace add /absolute/path/to/sdd-plugin

# then, in either case:
/plugin install sdd@gatsby
```

For pure local development without registering a marketplace:

```bash
claude --plugin-dir /absolute/path/to/sdd-plugin
```

Commands then appear **namespaced**: `/sdd:start`, `/sdd:spec`, `/sdd:plan`,
`/sdd:doc-investigation`, … Claude Code always prefixes a plugin's skills with its
`plugin.json` name (`sdd`), regardless of where the plugin came from — the namespace is
not tied to the source.

**Do not copy or symlink the `skills/` folders into `~/.claude/skills/`.** That loads
them as *standalone* skills, which are **unprefixed** — `/plan` then shadows the native
`/plan`, and you lose the `sdd:` grouping entirely. This is also why the skill folders
here carry no manual prefix (no `f-`, no `sdd-`): the namespace is supplied by the plugin
install, not by the folder name. If you ever see bare `/plan` / `/spec`, you have a
standalone copy loaded — remove it (e.g. `rm ~/.claude/skills/plan`) and re-install via
`/plugin`.

Verify after install:

```text
/help            # pipeline commands should all read /sdd:…
/plugin          # sdd@gatsby should be listed and enabled
```

---

## One-Time Setup

> **Windows users:** the plugin itself installs via `/plugin` in Claude Code (no shell installer), but the pipeline's helper scripts are bash + `python3` — run Claude Code under **WSL2** or **Git Bash**. Inside WSL/Git Bash, the `export VAR=value` / `~/.zshenv` / `~/.bashrc` instructions below work as-is.
>
> **WSL2 is the recommended Windows environment:** it ships `python3` and runs bash without extra setup. On **native Windows + Git Bash**, the Python installer often provides only `python` / `py` (no `python3`) — the `SessionStart` hook will create a `python3` shim, but WSL2 avoids the issue.
>
> If you prefer to set environment variables from **PowerShell** instead, the equivalents are:
> - Current session: `$env:JIRA_TOKEN = "your-token"` · `$env:CLAUDE_DOC_HOME = "C:\path\to\docs-registry"`
> - Persisted (user scope): `setx JIRA_TOKEN "your-token"` · `setx CLAUDE_DOC_HOME "C:\path\to\docs-registry"` — restart the shell afterwards so child processes inherit the value.
>
> Avoid `cmd.exe` for the install scripts; use WSL2 or Git Bash.

### Persistent Rules Files

- `${CLAUDE_PLUGIN_ROOT}/AGENTS.md` — global execution and safety constraints
- `./.claude/service-rules.md` — service-level business invariants in each consumer project
- `${CLAUDE_PLUGIN_ROOT}/lib/jira.sh` — direct Jira REST helper for `/sdd:start`

Template source installed with the SDD bundle:

- `${CLAUDE_PLUGIN_ROOT}/templates/service-rules.md`

`/sdd:start` reads both and writes compact reusable rules to `.specwork/_state/<slug>-rules.json`.
`/sdd:start` also initializes `.specwork/_state/<slug>-implementation-cache.json` for feature-local implementation memory.

### 1) Jira REST credentials (optional but recommended)

```zsh
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_USER="your.email@company.com"
export JIRA_TOKEN="your-atlassian-api-token"
```

Put those exports in `~/.zshenv` on macOS so non-interactive shells can see them.

Security note:
- Never store real credentials in this repository.
- Never commit `.env` files with Jira secrets.
- Keep only placeholders like `"your-atlassian-api-token"` in docs and examples.

For Jira Server/Data Center with bearer auth:

```zsh
export JIRA_BASE_URL="https://jira.your-company.internal"
export JIRA_AUTH_MODE="bearer"
export JIRA_TOKEN="your-personal-access-token"
```

Jira credentials are only needed when you pass a **Jira ticket key** to `/sdd:start`.
If you pass one without credentials configured, `/sdd:start` **stops immediately**
(no `.specwork/` artifacts are created) and tells you which variables to set — it
does **not** silently fall back to a placeholder. Free-text input needs no Jira.

### 2) `glab` (optional)

```bash
brew install glab
glab auth login
```

If `glab` is unavailable, MR and mr-address flows work in manual mode.

### 4) Documentation registry (optional)

The `/doc-*` and `/adr-*` commands read and write a
shared registry rooted at `$CLAUDE_DOC_HOME`:

```zsh
export CLAUDE_DOC_HOME="$HOME/path/to/shared-docs-registry"
```

When unset, it defaults to `~/.claude` (local-only). Point it at a synced or
shared directory so `/sdd:doc-catalog` and `/sdd:doc-adr` make catalog and decision
records discoverable across the team via `/sdd:ask`. The
commands create `service-catalog/` and `adr-registry/` subdirectories under it.

### 5) Project validation script (`commands/check.sh`)

`/sdd:mr` shells out to `bash commands/check.sh` in the project root to validate
the code before pushing (`/sdd:commit` does not run it). The pipeline treats
`exit 0` as clean and any non-zero exit as a stop signal.

This script is **project-owned** — each consumer repo provides one, commits it,
and the whole team (and the pipeline) uses the same definition of "the code
is green." A template ships with the skill:

```bash
# from the project root
mkdir -p commands
cp ${CLAUDE_PLUGIN_ROOT}/templates/check.sh.example commands/check.sh
chmod +x commands/check.sh
git add commands/check.sh
git commit -m "chore: add commands/check.sh for SDD pipeline validation"
```

The template auto-detects common stacks (Gradle, Maven, npm/pnpm/yarn,
pytest, Cargo, Go) and runs a sensible default. **Edit it** so it matches
what CI runs — otherwise local green and CI green will diverge. For Spring
Boot projects with a separate integration-test source set, uncomment the
`integrationTest` line so `clean check integrationTest spotlessCheck` runs
together.

What the script *should* do:

- Run the same commands CI runs (unit + integration + lint + format).
- Exit non-zero on any failure (`set -euo pipefail` at the top handles this).
- Avoid network calls, cache reliance, or randomness — runs should be
  reproducible.

What the script *should not* do:

- Talk to remote services (Jira, Slack, deploy endpoints).
- Mutate working state (no commits, no `git push`, no schema migrations).
- Run optional/slow workflows that aren't in CI (`./gradlew dependencyUpdates`,
  Renovate scans, etc.).

**Without `commands/check.sh`**, `/sdd:mr` falls back to asking how to validate
on every run (the 3-option prompt: full check / scoped tests / skip). Providing
the script removes that prompt and makes runs deterministic. `/sdd:commit`
similarly logs a warning and continues.

**Windows:** the file is bash. Run it through Git Bash or WSL2; the Gradle /
Maven / npm CLIs invoked inside work identically from those shells. Don't
write a `commands/check.cmd` PowerShell variant — the skill only invokes the
bash path.
