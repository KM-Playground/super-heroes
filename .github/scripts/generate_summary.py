#!/usr/bin/env python3
"""
Generate PR merge summary report and handle notifications
This script handles all processing and GitHub CLI calls in one place
"""

import os
import sys
import json
import subprocess
from datetime import datetime


def run_gh_command(command):
    """Run a GitHub CLI command and return the output"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.stderr}", file=sys.stderr)
        return None


def get_pr_author(pr_number):
    """Get the author of a PR using GitHub CLI"""
    author = run_gh_command(f"gh pr view {pr_number} --json author --jq '.author.login'")
    return author if author else "PR author"


def parse_environment_data():
    """Parse environment variables and return processed data"""
    total_requested_raw = os.getenv('TOTAL_REQUESTED_RAW', '')
    total_requested = len([pr.strip() for pr in total_requested_raw.split(',') if pr.strip()])
    
    spoc = os.getenv('SPOC', '')
    
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
        'spoc': spoc,
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
        summary += '\n'.join(f"- PR #{pr} (insufficient approvals, failing checks, or not targeting master)" 
                           for pr in data['unmergeable'])
    else:
        summary += "- None"
    
    summary += """

### Update with Master Failed
"""
    
    if data['failed_update']:
        summary += '\n'.join(f"- PR #{pr} (could not update branch with master)" 
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
*Workflow executed by @{data['spoc']}*"""
    
    return summary


def get_failure_messages():
    """Get the failure message templates"""
    return {
        'unmergeable': "❌ This PR could not be merged due to one or more of the following:\n\n- Less than 2 approvals\n- Failing or missing status checks\n- Not up-to-date with `master`\n- Not targeting `master`\n\nPlease address these issues to include it in the next merge cycle.",
        'failed_update': "❌ This PR could not be updated with the latest `master` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `master`.",
        'failed_ci': "❌ This PR's CI checks failed after being updated with `master`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `master` - please check if this caused any new test failures.",
        'timeout': "⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `master`.\n\nThe PR has been updated with the latest `master` - please check the CI status and re-run if needed.",
        'failed_merge': "❌ This PR failed to merge despite passing all checks. This may be due to a last-minute conflict or GitHub API issue.\n\nThe PR has been updated with the latest `master` - please try merging manually or contact the repository administrators."
    }


def comment_on_failed_prs(data):
    """Comment on all failed PRs with specific failure reasons"""
    failure_messages = get_failure_messages()
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
            message = f"@{author} @{data['spoc']}, {failure_messages[category]}"
            
            # Comment on PR
            success = run_gh_command(f'gh pr comment {pr_number} --body {json.dumps(message)}')
            if success is not None:
                print(f"✅ Commented on PR #{pr_number}")
            else:
                print(f"❌ Failed to comment on PR #{pr_number}")


def update_prs_with_master(prs_to_update):
    """Update PRs with master branch"""
    if not prs_to_update:
        return
        
    print(f"Updating {len(prs_to_update)} PRs with master: {', '.join(prs_to_update)}")
    
    for pr_number in prs_to_update:
        print(f"Updating PR #{pr_number} with master...")
        success = run_gh_command(f'gh pr update-branch {pr_number}')
        if success is not None:
            print(f"✅ Updated PR #{pr_number}")
        else:
            print(f"❌ Failed to update PR #{pr_number}")


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
        
        # Update PRs with master (for CI failures, timeouts, and merge failures)
        prs_to_update = data['failed_ci'] + data['timeout'] + data['failed_merge']
        update_prs_with_master(prs_to_update)
        
        print("PR notifications and updates completed successfully")
        
    except Exception as e:
        print(f"Failed to process PR notifications: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
