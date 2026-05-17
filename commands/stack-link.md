Retroactively register the parent of the current branch in the stacked-PRs system. Use this when you have an existing stack of branches created BEFORE adopting the stacked-prs skill, and you need to record the parent relationships so `/stack-sync` and `/stack-list` know about them.

Argument: `$ARGUMENTS` (optional) — the parent branch name. If omitted, the command auto-detects candidates.

Steps:

1. **Get the current branch:** `git rev-parse --abbrev-ref HEAD`. If it returns `main` or `master`, stop:
   > "You are on main. There is nothing to link."

2. **Check if a parent is already registered:**
   `git config branch.<current>.stack-parent`
   If it returns a value, ask:
   > "`<current>` already has a parent registered: `<existing>`. Overwrite, or cancel?"

3. **If `$ARGUMENTS` was provided as the parent:**
   - Verify the parent branch exists: `git rev-parse --verify "$ARGUMENTS"`.
   - If it doesn't exist locally, error out.
   - Skip to step 5.

4. **If no argument, detect candidates:**
   - List all `feat/AB*` and `fix/AB*` branches except the current one:
     `git for-each-ref --format='%(refname:short)' refs/heads/feat/AB* refs/heads/fix/AB*`
   - For each candidate, check if the current branch descends from it: `git merge-base --is-ancestor <candidate> HEAD` (exit code 0 means yes).
   - Of the candidates that are ancestors, rank by closeness: prefer the one with the smallest number of commits unique to the current branch (`git rev-list --count <candidate>..HEAD`).
   - Present the top 1-3 candidates with their commit-distance and ask the user which one is the parent. If there is a single strong match, confirm it:
     > "Detected `<X>` as the parent (you are <N> commits ahead of it). Confirm?"

5. **Set the config:**
   `git config branch.<current>.stack-parent <parent>`

6. **Show the resulting chain** by running `/stack-list`.

Notes:
- This command is read-only on git history — it only writes to `.git/config`.
- It does NOT validate that the chosen parent is sensible (e.g., that the user's branch was actually started from it). Trust the user's intent. The auto-detection is just a convenience.
