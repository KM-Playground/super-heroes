# Automated PR Merge Workflow Documentation

## Overview

The Automated PR Merge Workflow (`automated_pr_merge.yaml`) is a GitHub Actions workflow that automates the validation and merging of multiple pull requests into the default branch. This workflow is designed to streamline the merge process while ensuring proper validation and approval gates.

## Key Features

- **Manual Approval Gate**: Requires approval from designated team members before execution
- **Sequential PR Processing**: Processes PRs in chronological order (lowest PR number first)
- **Automated CI Testing**: Triggers CI tests for each PR before merging
- **Release Branch Support**: Optional support for merging release branches first
- **Comprehensive Validation**: Validates PR status, approvals, and mergeability
- **Detailed Reporting**: Provides comprehensive summary of merge results

## Prerequisites

Before using this workflow, you must complete the following setup steps:

### 1. Create a Fine-Grained Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click "Generate new token"
3. Configure the token with the following settings:
   - **Repository access**: Select the specific repository or repositories where this workflow will be used
   - **Repository permissions**:
     - **Administration**: Read access
     - **Code**: Read and Write access
     - **Metadata**: Read access
     - **Pull requests**: Read and Write access

4. Generate the token and copy it securely

### 2. Create the Merge Approvals Team

1. Go to your GitHub organization settings
2. Navigate to Teams
3. Create a new team named `merge-approvals`
4. Add all backend SPOCs (Subject Matter Point of Contacts) who should have approval rights for merge operations
5. Ensure team members have appropriate repository access

### 3. Create the Merge Queue Environment

1. Go to your repository Settings → Environments
2. Click "New environment"
3. Name it `merge_queue`
4. Configure the environment:
   - **Required reviewers**: Enable this option
   - Add the `merge-approvals` team as a required reviewer
   - **Deployment branches and tags**: Select "Protected branches only"
   - Ensure your default branch (e.g., `master` or `main`) appears in the protected branches list

### 4. Add Repository Secret

1. Go to your repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `CI_TRIGGER_TOKEN`
4. Value: The fine-grained personal access token created in step 1
5. Click "Add secret"

## How to Use the Workflow

### Triggering the Workflow

1. Navigate to your repository's Actions tab
2. Select "Merge Queue Drainer" workflow
3. Click "Run workflow"
4. Fill in the required parameters:
   - **PR Numbers**: Comma-separated list of PR numbers to merge (e.g., `123,124,125`)
   - **Release PR** (optional): PR number for a release branch to merge first
   - **Required Approvals** (optional): Override the default approval count from branch protection

### Workflow Execution Process

1. **Approval Gate**: The workflow will pause and wait for manual approval from a member of the `merge-approvals` team
2. **Release Merge** (if specified): Merges the release PR first
3. **PR Validation**: Validates all specified PRs for:
   - Existence and open status
   - Required approvals
   - Merge conflicts
   - Branch protection compliance
4. **Sequential Merging**: For each valid PR:
   - Updates the PR branch with the latest default branch
   - Triggers CI tests by commenting "ok to test"
   - Waits for CI completion (up to 45 minutes)
   - Merges the PR using squash merge
5. **Notification**: Sends a comprehensive summary of results

### Understanding the Results

The workflow categorizes PRs into different outcomes:

- **✅ Merged**: Successfully merged PRs
- **❌ Unmergeable**: PRs that failed initial validation (conflicts, insufficient approvals, etc.)
- **🔄 Failed Update**: PRs where branch update failed
- **🧪 Failed CI**: PRs where CI tests failed
- **⏰ Timeout**: PRs where CI tests didn't complete within 45 minutes
- **💥 Failed Merge**: PRs where the final merge operation failed

## Best Practices

### For Users

- Ensure all PRs are ready for merge before triggering the workflow
- Resolve any merge conflicts beforehand
- Verify that all required approvals are in place
- Use descriptive commit messages as the workflow uses squash merge

### For Administrators

- Regularly review and update the `merge-approvals` team membership
- Monitor workflow execution times and adjust timeouts if needed
- Keep the `CI_TRIGGER_TOKEN` secure and rotate it periodically
- Review branch protection rules to ensure they align with workflow expectations

## Troubleshooting

### Common Issues

**Workflow fails at approval gate**

- Ensure the user triggering the workflow is a member of the `merge-approvals` team
- Verify the `merge_queue` environment is properly configured

**CI tests don't trigger**

- Verify the `CI_TRIGGER_TOKEN` has the correct permissions
- Ensure the `pr-test.yaml` workflow is present and configured correctly
- Check that the token isn't expired

**PRs marked as unmergeable**

- Check for merge conflicts
- Verify required approvals are met
- Ensure PRs are targeting the correct base branch

**Merge failures**

- Review branch protection rules
- Check for last-minute changes that might cause conflicts
- Verify repository permissions

### Getting Help

If you encounter issues not covered in this documentation:
1. Check the workflow run logs for detailed error messages
2. Review the PR comments for specific failure reasons
3. Contact your repository administrators or the development team

## Security Considerations

- The `CI_TRIGGER_TOKEN` should be treated as a sensitive credential
- Only trusted team members should be added to the `merge-approvals` team
- Regularly audit team membership and token permissions
- Monitor workflow usage through GitHub's audit logs

## Workflow Dependencies

This workflow integrates with:
- **PR Test Runner** (`pr-test.yaml`): Handles CI testing when "ok to test" comments are made
- **Branch Protection Rules**: Enforces approval requirements and merge restrictions
- **GitHub Environments**: Provides the approval gate mechanism

Ensure these components are properly configured for optimal workflow performance.
