#!/usr/bin/env python3
"""
Generate PR merge summary report and handle notifications
This script handles all processing and GitHub CLI calls in one place
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import sys

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


@dataclass
class MergeQueueData:
    """Data class containing all merge queue workflow results and configuration"""
    default_branch: str
    required_approvals: str
    total_requested: int
    submitter: str
    original_issue_number: str
    merged: List[str]
    unmergeable: List[str]
    failed_update: List[str]
    failed_ci: List[str]
    timeout: List[str]
    startup_timeout: List[str]
    failed_merge: List[str]

    def as_dictionary(self) -> Dict[str, List[str]]:
        """Return all failure categories as a dictionary for easy iteration."""
        return {
            'unmergeable': self.unmergeable,
            'failed_update': self.failed_update,
            'failed_ci': self.failed_ci,
            'timeout': self.timeout,
            'startup_timeout': self.startup_timeout,
            'failed_merge': self.failed_merge
        }


def parse_environment_data() -> MergeQueueData:
    """Parse environment variables and return processed data"""
    total_requested_raw: str = os.getenv('TOTAL_REQUESTED_RAW', '')
    total_requested: int = len([pr.strip() for pr in total_requested_raw.split(',') if pr.strip()])

    default_branch: str = os.getenv('DEFAULT_BRANCH', 'main')
    required_approvals: str = os.getenv('REQUIRED_APPROVALS', '2')
    submitter: str = os.getenv('SUBMITTER', 'unknown')
    original_issue_number: str = os.getenv('ORIGINAL_ISSUE_NUMBER', '')

    def parse_comma_separated(env_var: str) -> List[str]:
        value: str = os.getenv(env_var, '')
        return [item.strip() for item in value.split(',') if item.strip()]

    merged: List[str] = parse_comma_separated('MERGED')

    # Parse UNMERGEABLE as JSON (it comes from validate-prs step as JSON)
    unmergeable: List[str] = []
    try:
        unmergeable_raw: str = os.getenv('UNMERGEABLE', '[]')
        unmergeable = json.loads(unmergeable_raw) if unmergeable_raw.strip() else []
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse UNMERGEABLE as JSON: {e}. Using empty list.", file=sys.stderr)
        unmergeable = []

    failed_update: List[str] = parse_comma_separated('FAILED_UPDATE')
    failed_ci: List[str] = parse_comma_separated('FAILED_CI')
    timeout: List[str] = parse_comma_separated('TIMEOUT')
    startup_timeout: List[str] = parse_comma_separated('STARTUP_TIMEOUT')
    failed_merge: List[str] = parse_comma_separated('FAILED_MERGE')

    return MergeQueueData(
        default_branch=default_branch,
        required_approvals=required_approvals,
        total_requested=total_requested,
        submitter=submitter,
        original_issue_number=original_issue_number,
        merged=merged,
        unmergeable=unmergeable,
        failed_update=failed_update,
        failed_ci=failed_ci,
        timeout=timeout,
        startup_timeout=startup_timeout,
        failed_merge=failed_merge
    )


def generate_summary_with_authors(data: MergeQueueData) -> str:
    """Generate the PR merge summary report with author information"""
    total_merged: int = len(data.merged)
    total_failed: int = (len(data.unmergeable) + len(data.failed_update) +
                        len(data.failed_ci) + len(data.timeout) + len(data.startup_timeout) + len(data.failed_merge))
    date: str = datetime.now().strftime('%Y-%m-%d')

    summary: str = f"""# PR Merge Summary - {date}

## Overview
- **Total PRs Requested**: {data.total_requested}
- **Successfully Merged**: {total_merged}
- **Failed to Merge**: {total_failed}

## Successfully Merged PRs ✅
"""

    if data.merged:
        summary += '\n'.join(f"- PR #{pr}" for pr in data.merged)
    else:
        summary += "- None"

    summary += """

## Failed PRs by Category ❌

### Initial Validation Failures
"""

    if data.unmergeable:
        for pr in data.unmergeable:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - insufficient approvals, failing checks, or not targeting {data.default_branch}"
    else:
        summary += "- None"

    summary += f"""

### Update with {data.default_branch.title()} Failed
"""

    if data.failed_update:
        for pr in data.failed_update:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - could not update branch with {data.default_branch}"
    else:
        summary += "- None"

    summary += """

### CI Checks Failed
"""

    if data.failed_ci:
        for pr in data.failed_ci:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI checks failed after update"
    else:
        summary += "- None"

    summary += """

### CI Execution Timeout
"""

    if data.timeout:
        for pr in data.timeout:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI did not complete within 45 minutes"
    else:
        summary += "- None"

    summary += """

### CI Startup Timeout
"""

    if data.startup_timeout:
        for pr in data.startup_timeout:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI workflow did not start within 5 minutes"
    else:
        summary += "- None"

    summary += """

### Merge Operation Failed
"""

    if data.failed_merge:
        for pr in data.failed_merge:
            author_result = GitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - merge command failed (likely merge conflicts)"
    else:
        summary += "- None"

    summary += f"""

---
@{data.submitter} - Your merge queue request has been completed!

*Automated workflow execution*"""

    return summary


def generate_summary(data: MergeQueueData) -> str:
    """Generate the PR merge summary report (legacy function for compatibility)"""
    return generate_summary_with_authors(data)


def get_failure_messages(default_branch: str, required_approvals: str) -> Dict[str, str]:
    """Get the failure message templates"""
    return {
        'unmergeable': f"❌ This PR could not be merged due to one or more of the following:\n\n- Less than {required_approvals} approvals\n- Failing or missing status checks\n- Not up-to-date with `{default_branch}`\n- Not targeting `{default_branch}`\n\nPlease address these issues to include it in the next merge cycle.",
        'failed_update': f"❌ This PR could not be updated with the latest `{default_branch}` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `{default_branch}`.",
        'failed_ci': f"❌ This PR's CI checks failed after being updated with `{default_branch}`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `{default_branch}` - please check if this caused any new test failures.",
        'timeout': f"⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `{default_branch}`.\n\nThe PR has been updated with the latest `{default_branch}` - please check the CI status and re-run if needed.",
        'startup_timeout': f"⏰ This PR's CI workflow did not start within the 5-minute startup timeout period after being triggered.\n\nThis may indicate issues with CI runner availability or workflow configuration. The PR has been updated with the latest `{default_branch}` - please check the CI status and re-trigger if needed.",
        'failed_merge': f"❌ This PR failed to merge despite passing all checks. This is most likely due to merge conflicts that occurred after other PRs were merged to `{default_branch}`.\n\n**If you received a merge conflict notification:** Please resolve the conflicts in your branch and push the changes.\n\n**If no conflicts were reported:** This may be due to a GitHub API issue. The PR has been updated with the latest `{default_branch}` - please try merging manually or contact the repository administrators."
    }


def comment_on_failed_prs(data: MergeQueueData) -> None:
    """Comment on all failed PRs with specific failure reasons"""
    failure_messages: Dict[str, str] = get_failure_messages(data.default_branch, data.required_approvals)
    failure_categories: Dict[str, List[str]] = data.as_dictionary()

    for category, prs in failure_categories.items():
        if not prs:
            continue

        for pr_number in prs:
            print(f"Commenting on PR #{pr_number} for {category} failure...")

            # Get PR author
            author_result = GitHubUtils.get_pr_author(pr_number)
            author: str = author_result.message

            # Build complete message
            message: str = f"@{author}, {failure_messages[category]}"

            # Comment on PR using shared utility
            GitHubUtils.comment_on_pr(str(pr_number), message)


def post_summary_to_original_issue(issue_number: str, summary: str, will_close: bool = True) -> None:
    """Post the merge queue summary to the original issue that triggered the workflow"""
    print(f"Posting summary to original issue #{issue_number}...")

    # Add a header to indicate this is the final summary
    if will_close:
        footer: str = "*This merge queue request has been completed. The issue will now be closed automatically.*"
    else:
        footer = "*This merge queue request encountered issues and requires manual review. The issue will remain open.*"

    final_summary: str = f"""## 🎯 **Merge Queue Results**

{summary}

---
{footer}"""

    result = GitHubUtils.comment_on_pr(str(issue_number), final_summary)
    if result.success:
        print(f"✅ Successfully posted summary to issue #{issue_number}")
    else:
        print(f"❌ Failed to post summary to issue #{issue_number}: {result.error_details}")
        raise Exception(f"Failed to post summary to issue #{issue_number}")


def close_original_issue(issue_number: str) -> None:
    """Close the original issue that triggered the merge queue workflow"""
    print(f"Closing original issue #{issue_number}...")

    close_comment: str = 'Merge queue workflow completed. This issue is now closed automatically.'
    result = GitHubUtils.close_issue_with_comment(str(issue_number), close_comment)
    if result.success:
        print(f"✅ Successfully closed issue #{issue_number}")
    else:
        print(f"❌ Failed to close issue #{issue_number}: {result.error_details}")
        # Don't raise exception for close failure - summary was already posted


def should_close_issue(data: MergeQueueData) -> bool:
    """
    Determine if the issue should be closed based on workflow results.

    Close the issue only if:
    1. At least one PR was requested for processing, AND
    2. The workflow completed successfully (not blocked by consecutive execution or other early failures)

    Returns:
        bool: True if issue should be closed, False otherwise
    """
    # If no PRs were requested, don't close (likely a configuration issue)
    if data.total_requested == 0:
        print("❌ No PRs were requested - issue will remain open for review")
        return False

    # If we have any results (merged or failed), it means the workflow processed PRs
    total_processed: int = (len(data.merged) + len(data.unmergeable) +
                           len(data.failed_update) + len(data.failed_ci) +
                           len(data.timeout) + len(data.startup_timeout) +
                           len(data.failed_merge))

    if total_processed > 0:
        print(f"✅ Workflow processed {total_processed} PRs - issue will be closed")
        return True
    else:
        print("❌ No PRs were processed - issue will remain open (likely blocked by consecutive execution or early failure)")
        return False


def main() -> None:
    """Main execution"""
    try:
        # Parse environment data
        data: MergeQueueData = parse_environment_data()

        # Display summary
        summary: str = generate_summary(data)
        print("=" * 50)
        print(summary)
        print("=" * 50)

        # Determine if issue should be closed
        should_close: bool = should_close_issue(data)

        # Post summary to original issue
        if data.original_issue_number:
            post_summary_to_original_issue(data.original_issue_number, summary, will_close=should_close)

            # Only close if workflow actually processed PRs
            if should_close:
                close_original_issue(data.original_issue_number)
            else:
                print(f"Issue #{data.original_issue_number} will remain open for manual review")
        else:
            print("Warning: No original issue number provided, skipping issue update")

        # Comment on failed PRs
        comment_on_failed_prs(data)

        print("PR notifications completed successfully")

    except Exception as e:
        print(f"Failed to process PR notifications: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
