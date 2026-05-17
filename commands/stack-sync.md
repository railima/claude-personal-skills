Cascade-rebase the current branch and all its descendants onto the new `main`, after a parent PR has merged. Use this when the root of your stack just merged on GitHub.

Steps:

1. **Pre-flight checks:**
   - Confirm git version >= 2.38 (for `--update-refs`): `git --version`. If older, follow the "Fallback" section at the bottom of this file.
   - Confirm clean working tree: `git status --short`. If anything is staged or unstaged, stop:
     > "Uncommitted changes detected. Commit, stash, or discard before running /stack-sync."
   - Get the current branch: `CURRENT=$(git rev-parse --abbrev-ref HEAD)`. If it's `main` or `master`, stop:
     > "You are on main — nothing to cascade."
   - Confirm the current branch has a stack-parent: `git config branch.$CURRENT.stack-parent`. If empty, stop:
     > "`$CURRENT` has no registered parent. Run /stack-link first, or check you're on the right branch."

2. **Walk up the chain to find the root parent:**
   - Start from `$CURRENT`, repeatedly read `git config branch.<X>.stack-parent` until you reach `main` (or a branch with no `stack-parent`).
   - Build the ordered list from root parent down to `$CURRENT`. Example: `[feat/AB100-foo, feat/AB101-bar, feat/AB102-baz, feat/AB103-deep]` where `feat/AB100-foo` is the root parent.
   - The "root parent" is the first element — the branch whose PR was merged.

3. **Confirm the root parent merged into main:**
   - `git fetch origin main`
   - Check containment: `git merge-base --is-ancestor <root-parent> origin/main` (exit code 0 means yes — its commits are in origin/main now).
   - If NOT contained, stop:
     > "Root parent `<X>` is NOT yet in origin/main. Are you sure its PR merged? Maybe you're syncing too early."

4. **Show the plan and ask for confirmation:**
   ```
   Plan:
   - Rebase current branch + descendants in one pass using --update-refs
   - Command: git rebase --onto origin/main <root-parent> <CURRENT> --update-refs
   - Branches that will be updated: <intermediate branches from the chain, excluding the root>
   - After success, the local branch <root-parent> will be offered for deletion (already in main).

   Proceed?
   ```

5. **Execute the cascade rebase:**
   `git rebase --onto origin/main <root-parent> $CURRENT --update-refs`

6. **Handle conflicts if they occur:**
   - If `git rebase` exits non-zero with conflicts, list the conflicting files and tell the user:
     > "Conflicts in: <files>. Resolve them, run `git add <files>`, then `git rebase --continue`. When the rebase finishes, tell me 'continue' and I'll wrap up the sync."
   - WAIT for the user to say "continue".
   - When they do, verify the rebase is no longer in progress (`git status` must NOT mention "rebase in progress" or "interactive rebase in progress"). If it still is, ask the user to finish it first.
   - Then proceed to step 7.

7. **Update the stack-parent of the formerly-second branch (the new root of the stack) to `main`:**
   - The branch that was directly under `<root-parent>` (call it `<second>`) is now planted on main.
   - `git config branch.<second>.stack-parent main`
   - **CRITICAL:** Do NOT touch the `stack-parent` of deeper branches. They still live on top of their immediate parents (which still exist as branches, just with rebased commits). Updating them all to `main` would flatten the stack, break `/stack-list`, and break the next `/stack-sync`.

   | Branch | Parent before sync | Parent after sync |
   |---|---|---|
   | second  (was child of root)  | root         | **main** (rewrite) |
   | third   (was child of second)| second       | second (unchanged) |
   | fourth  (was child of third) | third        | third (unchanged) |

8. **Offer to delete the local root branch:**
   > "Local branch `<root-parent>` is already in main (merged). Delete it? (`git branch -d <root-parent>`)"
   - Only delete on explicit user confirmation.
   - Use `-d` (safe delete), not `-D` (force). If git refuses, that means there are unmerged commits — investigate, don't override.

9. **Show the new state** by running `/stack-list`.

## Fallback for git < 2.38 (no --update-refs)

Manually cascade:

1. Capture old tips of each non-root branch in the chain:
   For each `<branch>` in chain except root: `OLD_<branch>=$(git rev-parse <branch>)`
2. Rebase the second branch (was child of root) onto main:
   `git checkout <second>` then `git rebase --onto origin/main <root-parent>`
3. For each subsequent branch in order:
   `git checkout <next>` then `git rebase --onto <prev-current-tip> $OLD_<prev>`
   where `<prev-current-tip>` is the new HEAD of the previous branch after its rebase.
4. Same conflict handling and same stack-parent rules at the end.

This path is slower and more error-prone — recommend the user upgrade git to >= 2.38 instead of relying on it.
