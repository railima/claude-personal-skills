---
name: stacked-prs
description: Use when working with dependent feature branches (stacked PRs) - e.g., feat/AB101-* branched off feat/AB100-* while AB#100's PR is still in review. Triggers on English phrases ("stacked PRs", "stacked branches", "dependent branches", "cascade rebase", "depends on the previous one", "start the next story that depends on this one", "the parent PR was merged") or Portuguese equivalents ("stacked PRs", "branches dependentes", "branches encadeadas", "rebase em cascata", "depende do anterior", "vou começar a próxima story que depende dessa", "o PR foi mergeado", "deu merge na main"); on the current branch having `git config branch.<name>.stack-parent` set; when about to create a feat/AB* branch while on another feat/AB*; and before any command that opens a PR when the current branch's stack-parent is not main.
---

# Stacked PRs

## What this skill is for

You are working on a chain of interdependent stories — typically `feat/AB100-*` -> `feat/AB101-*` -> `feat/AB102-*` and so on — and you don't want to block on PR review before starting the next story. Each branch is open as its own PR in dependency order. When a parent PR merges to main, every descendant needs to be rebased onto the new main so its PR shows only the commits for its own story.

This skill tracks parent relationships between branches and cascades the rebase work when a parent merges. It does NOT open PRs (you keep using your own commit/PR command) and it does NOT touch remote state on its own.

## State model (read this first)

Each child branch stores its parent in **git config**:

```
git config branch.<child-name>.stack-parent <parent-branch-name>
```

This lives in `.git/config` — local to the clone, never committed, survives rebases. No JSON manifest, no global state. The "stack" is the transitive chain: follow `stack-parent` upward until you hit `main` (or a branch with no `stack-parent`).

## The slash commands

- `/stack-new <id>` — branch a new dependent story off the current branch and register the parent link in one step.
- `/stack-link [parent-branch]` — retroactively register the parent of an existing branch (for branches created before adopting this skill).
- `/stack-sync` — cascade-rebase the current branch and all its descendants onto the new main, after the root parent has merged.
- `/stack-list` — show the stack from the current branch up to main, with PR status.

Read the command file before executing it — each one has its own step-by-step.

## When to invoke this skill (auto-triggers)

1. **User mentions stacking concepts** (in English or Portuguese):
   - EN: "stacked PRs", "stacked branches", "dependent branches", "cascade rebase", "depends on the previous one", "start the next dependent story", "the parent PR was merged"
   - PT: "stacked PRs", "branches dependentes", "branches encadeadas", "rebase em cascata", "depende do anterior", "vou começar a próxima story que depende dessa", "o PR foi mergeado", "deu merge na main", "PR pai mergeou", "preciso cascatear", "sincronizar a pilha"
2. **User is on a stack branch**: current branch matches `feat/<id>-*` or `fix/<id>-*` AND `git config branch.<current>.stack-parent` returns a value.
3. **A parent PR merged**: user says "the parent PR was merged" / "AB100 was merged into main" / "o 100 mergeou" / "deu merge na main" while on a branch with `stack-parent`.
4. **About to create a new feature branch from another feature branch**: user is on `feat/<X>-*` and is about to run `git checkout -b feat/<Y>-*` or start a new story. Ask if Y depends on X.
5. **About to open a PR on a branch whose `stack-parent` is not `main`**: warn that the PR will contain the parent's commits too unless `/stack-sync` is run first.

## Behavioral rules

### Never act silently
The skill detects, surfaces options, and waits for the user to say "go". Never auto-create a branch, auto-register a parent link, or auto-start a rebase.

### When the user is about to branch from a feature branch
Ask:
> "You are on `feat/<X>-foo`. Is the new branch a dependent continuation of this work, or independent (in which case I should branch from main)?"

- Dependent -> suggest `/stack-new <Y>` (creates from current + registers parent).
- Independent -> standard flow: `git checkout main && git checkout -b feat/<Y>-bar`.

### When the user says a parent PR merged
Suggest `/stack-sync` from the deepest branch in the stack they are actively working on:
> "The PR for <X> was merged. I see you have <Y>, <Z>, <W> stacked on top of it. Want me to run `/stack-sync` from <W> (the deepest) to cascade-rebase everything in one pass? If a conflict appears I will stop and let you know."

### Before opening a PR on a branch with non-main parent
Warn explicitly:
> "Heads up: you are on `feat/<Y>-bar` whose parent is `feat/<X>-foo`, not main. If you open the PR now, it will contain the commits from X as well. Recommended:
> 1. Wait for X to merge into main.
> 2. Run `/stack-sync` to replant Y onto main.
> 3. Then open the PR.
>
> Open the PR anyway, or wait?"

If the user insists, respect the decision — it's theirs to make.

## Critical detail: how `stack-parent` updates during `/stack-sync`

When parent A merges and the cascade rebases B -> C -> D onto main, **only B's `stack-parent` is rewritten** (to `main`). C and D keep their parents (B and C respectively) because those branches still exist — they have just been rebased to have new commits on top.

| Branch | Parent before sync | Parent after sync | Reason |
|---|---|---|---|
| B | A (merged, deleted) | **main** | Old parent no longer exists |
| C | B (still exists) | B | B is still its parent, just with new commits |
| D | C (still exists) | C | Same — only the parent's tip moved |

**Wrong implementation:** setting all of B, C, D to `stack-parent = main` after the cascade. This would flatten the stack in `/stack-list`, break the next `/stack-sync`, and lose the dependency structure.

The `stack-parent` represents "what branch this one is planted on top of," not "where these commits came from."

## Out of scope

- Opening PRs (the user keeps using their own commit/PR command against main after `/stack-sync`).
- Force-pushing or any operation that touches remote state.
- Auto-resolving merge conflicts (pause, instruct, resume).
- Branches that don't follow a `feat/<id>-*` or `fix/<id>-*` convention (adapt the patterns if your project uses a different convention).
