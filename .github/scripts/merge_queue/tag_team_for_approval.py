#!/usr/bin/env python3
"""
Tag merge-approvals team for approval.

This script posts an approval request comment to the issue,
tagging the merge-approvals team with all relevant details.
"""

import os
import sys
from typing import Optional

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def format_pr_numbers(pr_numbers: str) -> str:
    """
    Format comma-separated PR numbers with # prefix for GitHub linking.

    Args:
        pr_numbers: Comma-separated PR numbers (e.g., "123,456,789")

    Returns:
        Formatted PR numbers with # prefix (e.g., "#123, #456, #789")
    """
    if not pr_numbers or not pr_numbers.strip():
        return pr_numbers

    # Split by comma, strip whitespace, add # prefix, and rejoin
    formatted_prs = []
    for pr in pr_numbers.split(','):
        pr = pr.strip()
        if pr:
            # Add # prefix if not already present
            if not pr.startswith('#'):
                pr = f"#{pr}"
            formatted_prs.append(pr)

    return ', '.join(formatted_prs)


def get_team_tag_from_env() -> str:
    """
    Get team tag from environment variables set by the workflow.

    Returns:
        Team tag string (either individual members or team tag)
    """
    team_tag = GitHubUtils.get_env_var("TEAM_TAG", "")
    team_members = GitHubUtils.get_env_var("TEAM_MEMBERS", "")

    if team_tag:
        print(f"📧 Using team tag from workflow: {team_tag}")
        if team_members:
            print(f"✅ Individual members found: {team_members}")
        else:
            print(f"⚠️ Using fallback team tag")
        return team_tag
    else:
        # Fallback if environment variables not set
        repository = GitHubUtils.get_env_var("GITHUB_REPOSITORY", "")
        if repository:
            org = repository.split('/')[0]
            fallback_tag = f"@{org}/merge-approvals"
            print(f"⚠️ No team tag from workflow, using fallback: {fallback_tag}")
            return fallback_tag
        else:
            print(f"❌ No team information available")
            return "@merge-approvals"


def create_approval_message(commenter: str, pr_numbers: str, member_tags: str, release_pr: Optional[str] = None, timeout_minutes: int = 60, reminder_interval: int = 15) -> str:
    """
    Create the approval request message.

    Args:
        commenter: Username who requested the merge
        pr_numbers: Comma-separated PR numbers
        member_tags: String with team member tags
        release_pr: Optional release PR number
        timeout_minutes: Timeout in minutes for approval
        reminder_interval: Reminder interval in minutes

    Returns:
        Formatted approval request message
    """
    # Format PR numbers with # prefix for GitHub linking
    formatted_pr_numbers = format_pr_numbers(pr_numbers)

    # Build release PR info if provided
    release_info = ""
    if release_pr and release_pr.strip():
        release_info = f"\n• **Release PR**: #{release_pr.strip()}"

    approval_message = f"""{member_tags} 🚀 **Merge Queue Approval Requested**

**Requested by**: @{commenter}
**PR Numbers**: {formatted_pr_numbers}{release_info}

**Action Required**: Please review the PRs and approve this merge queue request.

⏰ **Timeout**: This request will timeout in {timeout_minutes} minutes if not approved.
📋 **Reminders**: You'll receive reminders every {reminder_interval} minutes.

**To approve**: Reply with 'approved'
**To reject**: Reply with 'rejected'

*This is an automated merge queue approval request.*"""

    return approval_message


def tag_team_for_approval(issue_number: int, commenter: str, pr_numbers: str, release_pr: Optional[str] = None) -> bool:
    """
    Tag the merge-approvals team for approval.

    Args:
        issue_number: Issue number to comment on
        commenter: Username who requested the merge
        pr_numbers: Comma-separated PR numbers
        release_pr: Optional release PR number

    Returns:
        True if successful, False otherwise
    """
    print(f"Tagging merge-approvals team for approval on issue #{issue_number}...")
    print(f"Requested by: @{commenter}")
    print(f"PR Numbers: {pr_numbers}")
    print(f"Release PR: {release_pr if release_pr else '(none)'}")

    # Get configurable timeout and reminder interval values
    timeout_minutes_str: str = GitHubUtils.get_env_var("APPROVAL_TIMEOUT_MINUTES", "60")
    reminder_interval_str: str = GitHubUtils.get_env_var("APPROVAL_REMINDER_INTERVAL_MINUTES", "15")

    # Convert to int with validation
    try:
        timeout_minutes: int = int(timeout_minutes_str)
        if timeout_minutes <= 0:
            timeout_minutes = 60
    except ValueError:
        timeout_minutes = 60

    try:
        reminder_interval: int = int(reminder_interval_str)
        if reminder_interval <= 0:
            reminder_interval = 15
    except ValueError:
        reminder_interval = 15

    print(f"Timeout: {timeout_minutes} minutes")
    print(f"Reminder interval: {reminder_interval} minutes")

    # Get team tag from environment variables (set by workflow)
    member_tags = get_team_tag_from_env()

    # Create the approval message
    approval_message = create_approval_message(commenter, pr_numbers, member_tags, release_pr, timeout_minutes, reminder_interval)

    # Post the comment
    result = GitHubUtils.add_comment(str(issue_number), approval_message)

    if result.success:
        print("✅ Successfully tagged merge-approvals team for approval")
        return True
    else:
        print(f"❌ Failed to tag team for approval: {result.error_details}")
        return False


def main() -> int:
    """Main function to tag team for approval."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    commenter: str = GitHubUtils.get_env_var("COMMENTER")
    pr_numbers: str = GitHubUtils.get_env_var("PR_NUMBERS")
    release_pr: str = GitHubUtils.get_env_var("RELEASE_PR", "")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    # Validate required parameters
    if not commenter:
        print("❌ Missing commenter information")
        return 1
    
    if not pr_numbers:
        print("❌ Missing PR numbers")
        return 1
    
    print("=== Team Approval Request ===")
    print(f"Issue: #{issue_number}")
    print(f"Commenter: @{commenter}")
    print(f"PR Numbers: {pr_numbers}")
    print(f"Release PR: {release_pr if release_pr else '(none)'}")
    print("=============================")
    
    # Tag the team for approval
    success = tag_team_for_approval(issue_number, commenter, pr_numbers, release_pr)
    
    if success:
        print("✅ Team tagging completed successfully")
        return 0
    else:
        print("❌ Team tagging failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
