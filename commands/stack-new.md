Create a new dependent feature branch from the current branch and register the parent link in one step. Use when starting a new story (`$ARGUMENTS`) that depends on the work in the current branch.

Steps:

1. **Verify current branch is a feature branch.** Run `git rev-parse --abbrev-ref HEAD`. If it doesn't match `feat/<id>-*` or `fix/<id>-*` (your project's convention), ask the user:
   > "You are on `<current>`, which is not a story branch. Do you want to (a) switch to main and create the new branch normally, or (b) use this branch as the parent anyway?"

2. **Confirm there are no uncommitted changes.** Run `git status --short`. If anything is staged or unstaged, stop:
   > "You have uncommitted changes on `<current>`. Commit or stash before creating the new branch."

3. **Fetch the work item from your tracker.**
   This is the project-specific part — replace with your tracker's API or CLI. Examples:

   - **Azure DevOps:**
     `az boards work-item show --id $ARGUMENTS --org https://dev.azure.com/<YOUR_ADO_ORG> --output json`
     Or via REST API with a PAT in `$AZURE_DEVOPS_EXT_PAT`:
     `curl -s -u ":$AZURE_DEVOPS_EXT_PAT" "https://dev.azure.com/<YOUR_ADO_ORG>/<YOUR_ADO_PROJECT>/_apis/wit/workitems/$ARGUMENTS?api-version=7.1&\$expand=all"`

   - **GitHub Issues:** `gh issue view $ARGUMENTS --json title,body,labels`
   - **Jira:** use the `jira` CLI or REST API.
   - **Linear:** use the Linear CLI or GraphQL API.

   If you don't have a tracker integration, just ask the user for a short slug and skip to step 5.

4. **Display the story** (title, type, state, description, acceptance criteria, tags) and ask the user to confirm before proceeding. If any acceptance criterion is ambiguous, ask clarifying questions one at a time.

5. **Create the new branch from the current branch:**
   - Derive a short kebab-case slug from the title.
   - `git checkout -b feat/<prefix>$ARGUMENTS-<slug>` (use whatever prefix matches your convention — e.g., `AB` for Azure Boards, no prefix for plain numeric IDs).
   - This creates from HEAD of the current branch, NOT from main — that's the whole point of this command.

6. **Register the parent link:**
   `git config branch.<new-branch>.stack-parent <previous-branch-name>`

7. **Confirm to the user:**
   ```
   Branch created: <new-branch>
   Parent registered: <previous-branch>

   Run /stack-list to see the full stack.
   ```

8. **Plan the implementation** with the user. A test-first plan that maps each acceptance criterion to one or more tests is recommended (red-green-refactor).

Rules:
- Do NOT push the branch yet — that happens at PR-opening time, AFTER the parent branch's PR is merged and you've run `/stack-sync`.
- If the user typed a non-numeric argument and your tracker requires a numeric ID, error out.
