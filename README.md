# Avengers
The Avengers are a team of superheroes from Marvel Comics, initially assembled to defend Earth against Loki's invasion.
More changes are going to be added to the avenger team.
some more changes.
even more changes.
Some more content being added for a release branch

## Merge Queue System

This repository includes an automated merge queue system that allows batch merging of pull requests through GitHub issue templates and workflows.

### Prerequisites

Before using the merge queue system, ensure the following labels exist in your repository:

- `merge-queue` - Issues related to merge queue operations
- `automation` - Issues related to automated processes and workflows

**Creating Required Labels:**

If these labels don't exist, create them using the GitHub CLI:

```bash
gh label create "merge-queue" --description "Issues related to merge queue operations" --color "0366d6"
gh label create "automation" --description "Issues related to automated processes and workflows" --color "f9d0c4"
```

### Using the Merge Queue

1. **Create a Merge Queue Request:**
   - Go to the Issues tab in GitHub
   - Click "New Issue"
   - Select "🚀 Merge Queue Request" template
   - Fill in the required information:
     - PR Numbers (comma-separated list)
     - Release PR (optional)
     - Required Approvals Override (optional)
     - PR Summary

2. **Trigger the Merge Process:**
   - After creating the issue, comment `begin-merge` on the issue
   - The system will automatically tag the `merge-approvals` team for approval
   - Wait for team approval (up to 60 minutes with 15-minute reminders)
   - Once approved, the merge queue workflow executes automatically

3. **Prerequisites for PRs:**
   - ✅ All PRs have required approvals
   - ✅ All CI tests are passing
   - ✅ No merge conflicts exist
   - ✅ PRs target the default branch
   - ✅ You are a member of the `merge-approvals` team

### Workflow Features

- **Sequential Processing:** PRs are processed in chronological order (lowest PR number first)
- **Timeout Protection:** 60-minute approval timeout with automatic reminders
- **Consecutive Prevention:** Only one merge process per issue to prevent conflicts
- **Automatic Cleanup:** Issues are automatically closed after successful completion
- **Error Handling:** Failed PRs are updated with the default integration branch and owners are notified

## Changelog

* Version 1
* Version 2
