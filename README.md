# claude-personal-skills

Personal collection of [Claude Code](https://claude.com/claude-code) skills and slash commands. These extend Claude Code's behavior with reusable workflows. Feel free to copy, adapt, or learn from them.

## What's in here

### Skills (`skills/`)

Auto-triggered behavioral guidance. When Claude detects a matching context, the skill content is loaded and shapes how Claude responds.

| Skill | What it does |
|---|---|
| [stacked-prs](skills/stacked-prs/SKILL.md) | Manages chains of dependent feature branches (stacked PRs). Tracks parent relationships in `git config`, cascades rebases when a parent PR merges, never touches remote state. |
| [cctree](skills/cctree/SKILL.md) | Organizes related Claude Code conversations into persistent session trees with bidirectional context recall, so work spanning multiple sessions inherits earlier decisions. Dependency-free (Python 3 stdlib), stores state in `~/.cctree`, no npm or MCP server. |

### Slash commands (`commands/`)

Explicit commands you invoke with `/<name>`. Pair with skills for full coverage (skills detect intent, commands execute).

| Command | Pairs with | What it does |
|---|---|---|
| `/stack-new <id>` | stacked-prs | Branch a new dependent story off the current branch and register the parent link. |
| `/stack-link [parent]` | stacked-prs | Retroactively register the parent of the current branch. |
| `/stack-sync` | stacked-prs | Cascade-rebase the current branch + descendants onto the new `main` after the root parent's PR merged. |
| `/stack-list` | stacked-prs | Show the current stack as an ASCII tree with PR status from GitHub. |

## Installation

Skills live under `~/.claude/skills/<name>/SKILL.md` and commands under `~/.claude/commands/<name>.md`. Both load globally across all your Claude Code sessions.

### Option A — Copy (simplest, no auto-updates)

```bash
git clone https://github.com/railima/claude-personal-skills.git
cp -R claude-personal-skills/skills/* ~/.claude/skills/
cp -R claude-personal-skills/commands/* ~/.claude/commands/
```

### Option B — Symlink (auto-updates when you `git pull`)

```bash
git clone https://github.com/railima/claude-personal-skills.git ~/code/claude-personal-skills
mkdir -p ~/.claude/skills ~/.claude/commands

# Symlink each skill directory
for skill in ~/code/claude-personal-skills/skills/*/; do
  name=$(basename "$skill")
  ln -s "$skill" ~/.claude/skills/"$name"
done

# Symlink each command file
for cmd in ~/code/claude-personal-skills/commands/*.md; do
  name=$(basename "$cmd")
  ln -s "$cmd" ~/.claude/commands/"$name"
done
```

Restart Claude Code (or start a new session) to pick up the new skills and commands.

## Workflow assumptions

These skills were designed around a workflow with:

- A work-item tracker that exposes ticket IDs via CLI or API (e.g., Azure DevOps, Jira, Linear, GitHub Issues)
- GitHub for source control
- A branch naming convention that embeds the ticket ID — `feat/<id>-<short-slug>` or similar

The `stack-new` command includes an example ADO API call you'll want to customize for your tracker (replace the placeholder org/project, or swap the whole fetch block for your tracker's CLI/API).

If your branch naming convention is different from `feat/AB<id>-*`, adjust the patterns in `stack-link` (the auto-detection scan) and in the `stacked-prs` skill triggers.

## Contributing

This is primarily a personal collection, but if a skill is broken or you have an improvement, issues and PRs are welcome.

## License

MIT — see [LICENSE](LICENSE).
