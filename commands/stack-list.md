Show the current stack — the chain of branches from the current branch up to `main`, plus any descendants below the current branch, with PR status from GitHub when available. Read-only.

Steps:

1. **Walk the chain from the current branch upward:**
   - Start at `git rev-parse --abbrev-ref HEAD`.
   - Repeatedly read `git config branch.<X>.stack-parent` until you reach `main`, empty, or detect a cycle (bail with an error if a cycle is found — the user has bad config).
   - You now have an ordered list from root to current.

2. **Walk descendants of the current branch (for visual completeness):**
   - List all `stack-parent` entries: `git config --get-regexp '^branch\..*\.stack-parent$'`
   - Parse `branch.<name>.stack-parent <value>` lines into a map of parent -> [children].
   - Starting from the current branch, recursively collect descendants. Show forks (multiple children of the same parent) as parallel sub-trees.

3. **For each branch in the tree, gather:**
   - Commits ahead of its parent: `git rev-list --count <parent>..<branch>`
   - Whether it's pushed to origin: `git rev-parse --verify origin/<branch>` (exit 0 = exists on remote)
   - If pushed AND `gh` is available, PR status: `gh pr view <branch> --json state,number 2>/dev/null`
     - State will be `OPEN`, `MERGED`, `CLOSED`, or `DRAFT`. Show as `[PR #42 OPEN]`.
     - If no PR exists, show `[no PR]`.
     - If gh fails or isn't installed, just omit the PR column.

4. **Render as an ASCII tree:**

   ```
   main
    └─ feat/AB100-foo     [PR #42 OPEN]      3 commits
        └─ feat/AB101-bar     [no PR]        5 commits
            └─ feat/AB102-baz     [no PR]    2 commits  ← you are here
                └─ feat/AB103-deep    [no PR] 1 commit
   ```

   - Mark the current branch with `← you are here`.
   - For forks, render parallel sub-trees with their own indent levels.
   - Align columns for readability when there are >2 branches.

5. **If the current branch has no `stack-parent`:**
   > "`<current>` is not part of a registered stack. Run /stack-link to register a parent, or this branch is just a regular feature branch."

   But still show whether it has descendants registered (someone may have stacked off it).

This command makes ZERO changes. It only reads git state and the GitHub API.
