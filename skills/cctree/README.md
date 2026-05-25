# cctree (skill)

Organize related Claude Code conversations into persistent, searchable **session
trees** with bidirectional context recall. Each session inherits what earlier
sibling sessions decided — no re-explaining.

This is the **standalone skill port** of [cctree](https://github.com/railima/cctree).
It needs no npm package and no MCP server: just Python 3 (stdlib only). State is
stored in `~/.cctree`, the same layout the full CLI uses, so the two interoperate.

## What it does

- **Organize** — group conversations into trees by release, sprint, or topic;
  tag, list, search, and export them.
- **Recall** — at the start of work, load the accumulated TL;DR + Decisions +
  Artifacts of every committed sibling into the current conversation.
- **Commit** — store a structured summary of a session so later siblings inherit
  the high-signal parts while verbose detail stays on disk for on-demand recall.

## What it does not do (vs. the full CLI)

A skill runs *inside* an existing session, so it cannot inject context into a new
session's system prompt at boot — recall is an explicit step here. It also does
not launch/resume Claude sessions or manage git worktrees. For those, install the
full tool: `npm i -g @railima/cctree`.

## Install

Drop the `cctree/` folder into your skills location (e.g. a personal skills repo,
or `~/.claude/skills/cctree/`). Claude reads `SKILL.md` and drives
`scripts/cctree.py` for you.

## Layout

```
cctree/
  SKILL.md            # instructions Claude follows
  scripts/cctree.py   # self-contained helper (Python 3, stdlib only)
```

MIT licensed.
