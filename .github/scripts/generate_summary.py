#!/usr/bin/env python3
"""
Generate PR merge summary report and handle notifications
This script handles all processing and GitHub CLI calls in one place
"""

import os
import sys
import json
from datetime import datetime

from gh_utils import get_pr_author, comment_on_pr, update_pr_branch, run_gh_command


def parse_environment_data():
    """Parse environment variables and return processed data"""
    total_requested_raw = os.getenv('TOTAL_REQUESTED_RAW', '')
    total_requested = len([pr.strip() for pr in total_requested_raw.split(',') if pr.strip()])

    default_branch = os.getenv('DEFAULT_BRANCH', 'main')
    required_approvals = os.getenv('REQUIRED_APPROVALS', '2')
    submitter = os.getenv('SUBMITTER', 'unknown')
    
    def parse_comma_separated(env_var):
        value = os.getenv(env_var, '')
        return [item.strip() for item in value.split(',') if item.strip()]
    
    merged = parse_comma_separated('MERGED')

    # Parse UNMERGEABLE as JSON (it comes from validate-prs step as JSON)
    try:
        unmergeable_raw = os.getenv('UNMERGEABLE', '[]')
        unmergeable = json.loads(unmergeable_raw) if unmergeable_raw.strip() else []
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse UNMERGEABLE as JSON: {e}. Using empty list.", file=sys.stderr)
        unmergeable = []

    failed_update = parse_comma_separated('FAILED_UPDATE')
    failed_ci = parse_comma_separated('FAILED_CI')
    timeout = parse_comma_separated('TIMEOUT')
    startup_timeout = parse_comma_separated('STARTUP_TIMEOUT')
    failed_merge = parse_comma_separated('FAILED_MERGE')
    
    return {
        'default_branch': default_branch,
        'required_approvals': required_approvals,
        'total_requested': total_requested,
        'submitter': submitter,
        'merged': merged,
        'unmergeable': unmergeable,
        'failed_update': failed_update,
        'failed_ci': failed_ci,
        'timeout': timeout,
        'startup_timeout': startup_timeout,
        'failed_merge': failed_merge
    }


def generate_summary_with_authors(data):
    """Generate the PR merge summary report with author information"""
    total_merged = len(data['merged'])
    total_failed = (len(data['unmergeable']) + len(data['failed_update']) +
                   len(data['failed_ci']) + len(data['timeout']) + len(data['startup_timeout']) + len(data['failed_merge']))
    date = datetime.now().strftime('%Y-%m-%d')

    summary = f"""# PR Merge Summary - {date}

## Overview
- **Total PRs Requested**: {data['total_requested']}
- **Successfully Merged**: {total_merged}
- **Failed to Merge**: {total_failed}

## Successfully Merged PRs ✅
"""

    if data['merged']:
        summary += '\n'.join(f"- PR #{pr}" for pr in data['merged'])
    else:
        summary += "- None"

    summary += """

## Failed PRs by Category ❌

### Initial Validation Failures
"""

    if data['unmergeable']:
        for pr in data['unmergeable']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - insufficient approvals, failing checks, or not targeting {data['default_branch']}"
    else:
        summary += "- None"

    summary += f"""

### Update with {data['default_branch'].title()} Failed
"""

    if data['failed_update']:
        for pr in data['failed_update']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - could not update branch with {data['default_branch']}"
    else:
        summary += "- None"

    summary += """

### CI Checks Failed
"""

    if data['failed_ci']:
        for pr in data['failed_ci']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - CI checks failed after update"
    else:
        summary += "- None"

    summary += """

### CI Execution Timeout
"""

    if data['timeout']:
        for pr in data['timeout']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - CI did not complete within 45 minutes"
    else:
        summary += "- None"

    summary += """

### CI Startup Timeout
"""

    if data['startup_timeout']:
        for pr in data['startup_timeout']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - CI workflow did not start within 5 minutes"
    else:
        summary += "- None"

    summary += """

### Merge Operation Failed
"""

    if data['failed_merge']:
        for pr in data['failed_merge']:
            author = get_pr_author(str(pr))
            summary += f"\n- PR #{pr} (@{author}) - merge command failed (likely merge conflicts)"
    else:
        summary += "- None"

    summary += f"""

---
@{data.get('submitter', 'unknown')} - Your merge queue request has been completed!

*Automated workflow execution*"""

    return summary


def generate_summary(data):
    """Generate the PR merge summary report (legacy function for compatibility)"""
    return generate_summary_with_authors(data)


def get_failure_messages(default_branch, required_approvals):
    """Get the failure message templates"""
    return {
        'unmergeable': f"❌ This PR could not be merged due to one or more of the following:\n\n- Less than {required_approvals} approvals\n- Failing or missing status checks\n- Not up-to-date with `{default_branch}`\n- Not targeting `{default_branch}`\n\nPlease address these issues to include it in the next merge cycle.",
        'failed_update': f"❌ This PR could not be updated with the latest `{default_branch}` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `{default_branch}`.",
        'failed_ci': f"❌ This PR's CI checks failed after being updated with `{default_branch}`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `{default_branch}` - please check if this caused any new test failures.",
        'timeout': f"⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `{default_branch}`.\n\nThe PR has been updated with the latest `{default_branch}` - please check the CI status and re-run if needed.",
        'startup_timeout': f"⏰ This PR's CI workflow did not start within the 5-minute startup timeout period after being triggered.\n\nThis may indicate issues with CI runner availability or workflow configuration. The PR has been updated with the latest `{default_branch}` - please check the CI status and re-trigger if needed.",
        'failed_merge': f"❌ This PR failed to merge despite passing all checks. This is most likely due to merge conflicts that occurred after other PRs were merged to `{default_branch}`.\n\n**If you received a merge conflict notification:** Please resolve the conflicts in your branch and push the changes.\n\n**If no conflicts were reported:** This may be due to a GitHub API issue. The PR has been updated with the latest `{default_branch}` - please try merging manually or contact the repository administrators."
    }


def comment_on_failed_prs(data):
    """Comment on all failed PRs with specific failure reasons"""
    failure_messages = get_failure_messages(data['default_branch'], data['required_approvals'])
    failure_categories = {
        'unmergeable': data['unmergeable'],
        'failed_update': data['failed_update'],
        'failed_ci': data['failed_ci'],
        'timeout': data['timeout'],
        'startup_timeout': data['startup_timeout'],
        'failed_merge': data['failed_merge']
    }
    
    for category, prs in failure_categories.items():
        if not prs:
            continue
            
        for pr_number in prs:
            print(f"Commenting on PR #{pr_number} for {category} failure...")
            
            # Get PR author
            author = get_pr_author(pr_number)
            
            # Build complete message
            message = f"@{author}, {failure_messages[category]}"
            
            # Comment on PR using shared utility
            comment_on_pr(str(pr_number), message)


def update_prs_with_default_branch(prs_to_update, default_branch):
    """Update PRs with default branch"""
    if not prs_to_update:
        return

    print(f"Updating {len(prs_to_update)} PRs with {default_branch}: {', '.join(prs_to_update)}")

    for pr_number in prs_to_update:
        print(f"Updating PR #{pr_number} with {default_branch}...")
        update_pr_branch(str(pr_number))


def find_or_create_commentary_issue():
    """Find existing 'Merge Queue Commentary' issue or create one"""
    try:
        # Search for existing issue with title and label
        print("Searching for existing 'Merge Queue Commentary' issue...")
        result = run_gh_command([
            'issue', 'list',
            '--label', 'commentary',
            '--state', 'open',
            '--search', 'Merge Queue Commentary in:title',
            '--json', 'number,title'
        ])

        if not result[0]:
            raise Exception(f"Failed to search for issues: {result[2]}")

        issues = json.loads(result[1])

        # Check if we found the exact issue
        for issue in issues:
            if issue['title'] == 'Merge Queue Commentary':
                print(f"Found existing commentary issue #{issue['number']}")
                return issue['number']

        # Issue not found, create it
        print("Commentary issue not found, creating new one...")

        # First, ensure the 'commentary' label exists
        print("Ensuring 'commentary' label exists...")
        label_result = run_gh_command([
            'label', 'create', 'commentary',
            '--description', 'Issues for automated workflow commentary',
            '--color', '0366d6'
        ])

        if not label_result[0]:
            # Label might already exist, check if that's the case
            if 'already exists' not in label_result[2].lower():
                print(f"Warning: Could not create 'commentary' label: {label_result[2]}")
            else:
                print("Label 'commentary' already exists")
        else:
            print("Created 'commentary' label")

        # Now create the issue
        result = run_gh_command([
            'issue', 'create',
            '--title', 'Merge Queue Commentary',
            '--body', 'This issue tracks automated PR merge queue execution summaries.',
            '--label', 'commentary'
        ])

        if not result[0]:
            raise Exception(f"Failed to create issue: {result[2]}")

        # Extract issue number from the created issue URL
        # Format: https://github.com/owner/repo/issues/123
        issue_url = result[1].strip()
        issue_number = issue_url.split('/')[-1]
        print(f"Created new commentary issue #{issue_number}")
        return int(issue_number)

    except Exception as e:
        print(f"Error finding/creating commentary issue: {e}", file=sys.stderr)
        raise


def add_summary_comment(issue_number, summary):
    """Add summary as comment to the commentary issue"""
    try:
        print(f"Adding summary comment to issue #{issue_number}...")

        # Add timestamp and format the comment
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        comment_body = f"## Workflow Execution - {timestamp}\n\n{summary}"

        result = run_gh_command([
            'issue', 'comment', str(issue_number),
            '--body', comment_body
        ])

        if not result[0]:
            raise Exception(f"Failed to add comment: {result[2]}")

        print(f"Successfully added summary comment to issue #{issue_number}")

    except Exception as e:
        print(f"Error adding comment to issue #{issue_number}: {e}", file=sys.stderr)
        raise


def main():
    """Main execution"""
    try:
        # Parse environment data
        data = parse_environment_data()

        # Display summary
        summary = generate_summary(data)
        print("=" * 50)
        print(summary)
        print("=" * 50)

        # Add summary to commentary issue
        issue_number = find_or_create_commentary_issue()
        add_summary_comment(issue_number, summary)

        # Comment on failed PRs
        comment_on_failed_prs(data)

        # Update PRs with default branch (for CI failures, timeouts, and merge failures)
        prs_to_update = data['failed_ci'] + data['timeout'] + data['startup_timeout'] + data['failed_merge']
        update_prs_with_default_branch(prs_to_update, data['default_branch'])

        print("PR notifications and updates completed successfully")

    except Exception as e:
        print(f"Failed to process PR notifications: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
