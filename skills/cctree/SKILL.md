---
name: cctree
description: >-
  Organize related Claude Code conversations into persistent, searchable session
  trees with bidirectional context recall. Use when work spans multiple sessions
  (a release, sprint, bug investigation, or long-running topic) and you want each
  session to inherit what earlier sibling sessions decided — without re-explaining.
  Invoke to start a tree, register a session, recall accumulated context at the
  start of work, commit a structured summary when work is done, recall a specific
  sibling's notes, or search/list/export past sessions. Standalone: stores state
  in ~/.cctree, no npm package or MCP server required.
argument-hint: "[init|branch|context|commit|recall|list|find|status|use|report|mermaid] ..."
---

# cctree

A **tree** is a durable folder on disk (`~/.cctree`) — not a Claude session, so it
burns no context window. Under a tree you register **child sessions**, do the work
in a normal conversation, and **commit** a structured summary back. Every later
session inherits the layered TL;DR + Decisions + Artifacts of every committed
sibling, so you never re-explain what was already decided.

This is the standalone skill port of the `cctree` tool. The npm package injects
sibling context into a new session's system prompt automatically via an MCP
server. A skill runs *inside* a session and cannot do that boot-time injection, so
here **recall is an explicit step you run at the start of work** (see "Start
working" below). The on-disk format is identical, so if the user also has the
`cctree` CLI installed, both read and write the same `~/.cctree` store.

## The helper script

All stateful operations go through the bundled helper. Run it with `python3`
(stdlib only, Python ≥ 3.8). Resolve its path relative to this SKILL.md file —
it lives at `scripts/cctree.py` next to this file. In the commands below it is
written as `cctree.py` for brevity; always invoke the real path, e.g.:

```
python3 /path/to/skills/cctree/scripts/cctree.py status
```

Never hand-edit files under `~/.cctree` — the script keeps `tree.json`,
`context.md`, and per-session summaries consistent.

## When to use this skill

- The user is about to start a piece of work that relates to earlier sessions
  ("continue on the payments feature", "next ticket in the sprint").
- The user wants the current session's outcome to be available to future
  sessions ("commit what we decided", "save this for later").
- The user asks "what did we decide about X?" / "did I ever work on Y?".
- The user wants to organize, search, or report on past work.

If the user just types `/cctree` with no clear intent, run `status` and `list`,
show them where they are, and ask what they want to do.

## Core workflow

### 1. Create a tree (once per release / sprint / topic)

```
cctree.py init "Payment Integration" --context docs/spec.md docs/api.md
```

`--context` copies reference files in as shared initial context for every
session. Pick a tree shape that fits the work:

| Tree = | Children = |
| --- | --- |
| a release / feature | research → POC → implementation → polish |
| one sprint | one ticket per child (tag with ticket IDs) |
| a long-running topic | each notable conversation, dated and tagged |

### 2. Register a session when you start working on a sub-task

```
cctree.py branch "Database Schema" --tags ticket-1234,schema
```

This records the session and makes it the active one. It does **not** open a new
Claude session — you are already in one.

### 3. Load accumulated context (this replaces the MCP auto-injection)

Immediately after `branch` — and whenever you resume work on a tree — run:

```
cctree.py context
```

Read the output and treat it as authoritative project context for the rest of
the conversation: it contains the shared initial context plus the TL;DR +
Decisions + Artifacts of every committed sibling. Briefly tell the user what was
inherited (e.g. "Loaded context: 3 committed sessions; Stripe was chosen in
Provider Research") so they know it's in scope. Do this proactively at the start
of related work, not only when asked.

### 4. Commit a structured summary when the work is done

When a session reaches a natural stopping point (or the user says "commit"),
write a summary and store it. Write the summary to a temp file, or pipe via
`--stdin`:

```
cctree.py commit "Database Schema" --stdin <<'EOF'
## TL;DR
One-paragraph plain-language outcome of this session.

## Decisions
- Each decision as its own bullet, stated as a conclusion not a discussion
- Include the *why* in one clause when it isn't obvious

## Artifacts
- path/to/file.ts — what it is
- PR #123, migration 0042, etc.

## Open Questions
- Anything unresolved that a later session should pick up

## Next Steps
- Concrete follow-ups

## Details
Longer narrative, reasoning, dead-ends. Stays on disk; NOT injected into
siblings, so be as verbose as useful here.
EOF
```

**Section contract — this is what makes the context bus compact:**
- Only `## TL;DR`, `## Decisions`, and `## Artifacts` are injected into siblings.
  Keep them tight and high-signal.
- `## Open Questions`, `## Next Steps`, and `## Details` are stored but **not**
  injected — they're read on demand via `recall`. Put verbose material here.
- Headers are matched case-insensitively; Portuguese equivalents also work
  (`## Resumo`, `## Decisões`, `## Artefatos`, `## Perguntas abertas`,
  `## Próximos passos`, `## Detalhes`).
- A summary with no recognized TL;DR/Decisions still commits, but the whole text
  gets injected verbatim — the script warns when this happens. Prefer the
  structure.

After committing, the next session that runs `context` inherits this summary
automatically.

### 5. Recall one sibling's full notes on demand

When the injected TL;DR isn't enough and you need a specific session's full
reasoning (including its `## Details` and `## Open Questions`):

```
cctree.py recall "Provider Research"
```

This is the equivalent of the npm tool's `get_sibling_context` — use it instead
of telling the user to go re-open the other session.

## Organizing and reviewing

```
cctree.py status                      # active tree + session, counts
cctree.py list                        # the active tree
cctree.py list --all                  # every tree
cctree.py list --tag bug              # filter by tag
cctree.py list --search oauth         # filter within a tree
cctree.py find "stripe"               # search names/tags/TL;DR/decisions/artifacts across ALL trees
cctree.py use "Sprint 23"             # switch the active tree
cctree.py abandon "Spike" [--delete]  # mark abandoned (or delete entirely)
```

Status markers in listings: `[x]` committed · `[ ]` active · `[~]` abandoned.

## Exports

```
cctree.py report "Payment Integration"   # markdown progress report (decisions, open questions, timeline, structure)
cctree.py mermaid                         # Mermaid graph of all trees
cctree.py mermaid --tree payment-integration
```

`report` and `mermaid` produce structural views deterministically. For an
**architecture diagram** (components, flows, and the reasoning behind decisions),
don't shell out — you are an LLM already: run `cctree.py context` plus
`recall` on the relevant sessions, then synthesize a Mermaid `graph`/`flowchart`
yourself from the committed decisions and artifacts. That replaces the npm tool's
`export mermaid --architecture` (which needs an API key) at no extra cost.

## Notes

- State lives in `~/.cctree` (override with the `CCTREE_HOME` env var, handy for
  testing). Back it up / commit it elsewhere if it matters — it is not in any
  project repo by default.
- Slugs are derived from names (lowercased, spaces → hyphens). Most commands
  accept either the display name or the slug.
- This skill never launches or resumes Claude sessions and never touches git
  worktrees — those are CLI-only features of the full `cctree` package. If the
  user needs them, point them to `npm i -g @railima/cctree`.
