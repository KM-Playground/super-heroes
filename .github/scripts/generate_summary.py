#!/usr/bin/env python3
"""
Generate PR merge summary report and handle notifications
This script handles all processing and GitHub CLI calls in one place
"""

import os
import sys
import json
from datetime import datetime

from gh_utils import get_pr_author, comment_on_pr, update_pr_branch


def parse_environment_data():
    """Parse environment variables and return processed data"""
    total_requested_raw = os.getenv('TOTAL_REQUESTED_RAW', '')
    total_requested = len([pr.strip() for pr in total_requested_raw.split(',') if pr.strip()])

    default_branch = os.getenv('DEFAULT_BRANCH', 'main')
    required_approvals = os.getenv('REQUIRED_APPROVALS', '2')
    
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
    failed_merge = parse_comma_separated('FAILED_MERGE')
    
    return {
        'default_branch': default_branch,
        'required_approvals': required_approvals,
        'total_requested': total_requested,
        'merged': merged,
        'unmergeable': unmergeable,
        'failed_update': failed_update,
        'failed_ci': failed_ci,
        'timeout': timeout,
        'failed_merge': failed_merge
    }


def generate_summary(data):
    """Generate the PR merge summary report"""
    total_merged = len(data['merged'])
    total_failed = (len(data['unmergeable']) + len(data['failed_update']) + 
                   len(data['failed_ci']) + len(data['timeout']) + len(data['failed_merge']))
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
        summary += '\n'.join(f"- PR #{pr} (insufficient approvals, failing checks, or not targeting {data['default_branch']})"
                           for pr in data['unmergeable'])
    else:
        summary += "- None"

    summary += f"""

### Update with {data['default_branch'].title()} Failed
"""

    if data['failed_update']:
        summary += '\n'.join(f"- PR #{pr} (could not update branch with {data['default_branch']})"
                           for pr in data['failed_update'])
    else:
        summary += "- None"
    
    summary += """

### CI Checks Failed
"""
    
    if data['failed_ci']:
        summary += '\n'.join(f"- PR #{pr} (CI checks failed after update)" 
                           for pr in data['failed_ci'])
    else:
        summary += "- None"
    
    summary += """

### CI Timeout
"""
    
    if data['timeout']:
        summary += '\n'.join(f"- PR #{pr} (CI did not complete within 45 minutes)" 
                           for pr in data['timeout'])
    else:
        summary += "- None"
    
    summary += """

### Merge Operation Failed
"""
    
    if data['failed_merge']:
        summary += '\n'.join(f"- PR #{pr} (merge command failed)" 
                           for pr in data['failed_merge'])
    else:
        summary += "- None"
    
    summary += f"""

---
*Automated workflow execution*"""
    
    return summary


def get_failure_messages(default_branch, required_approvals):
    """Get the failure message templates"""
    return {
        'unmergeable': f"❌ This PR could not be merged due to one or more of the following:\n\n- Less than {required_approvals} approvals\n- Failing or missing status checks\n- Not up-to-date with `{default_branch}`\n- Not targeting `{default_branch}`\n\nPlease address these issues to include it in the next merge cycle.",
        'failed_update': f"❌ This PR could not be updated with the latest `{default_branch}` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `{default_branch}`.",
        'failed_ci': f"❌ This PR's CI checks failed after being updated with `{default_branch}`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `{default_branch}` - please check if this caused any new test failures.",
        'timeout': f"⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `{default_branch}`.\n\nThe PR has been updated with the latest `{default_branch}` - please check the CI status and re-run if needed.",
        'failed_merge': f"❌ This PR failed to merge despite passing all checks. This may be due to a last-minute conflict or GitHub API issue.\n\nThe PR has been updated with the latest `{default_branch}` - please try merging manually or contact the repository administrators."
    }


def comment_on_failed_prs(data):
    """Comment on all failed PRs with specific failure reasons"""
    failure_messages = get_failure_messages(data['default_branch'], data['required_approvals'])
    failure_categories = {
        'unmergeable': data['unmergeable'],
        'failed_update': data['failed_update'],
        'failed_ci': data['failed_ci'],
        'timeout': data['timeout'],
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
        
        # Comment on failed PRs
        comment_on_failed_prs(data)
        
        # Update PRs with default branch (for CI failures, timeouts, and merge failures)
        prs_to_update = data['failed_ci'] + data['timeout'] + data['failed_merge']
        update_prs_with_default_branch(prs_to_update, data['default_branch'])
        
        print("PR notifications and updates completed successfully")
        
    except Exception as e:
        print(f"Failed to process PR notifications: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
