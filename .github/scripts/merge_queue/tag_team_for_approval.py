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


def get_team_members_for_tagging(org: str, team: str) -> str:
    """
    Get team members and format them for individual tagging.

    Args:
        org: Organization name
        team: Team name/slug

    Returns:
        String with individual member tags, or fallback team tag
    """
    members = GitHubUtils.get_team_members(org, team)

    if not members:
        print(f"⚠️ Could not retrieve team members for {org}/{team}, using team tag as fallback")
        return f"@{org}/{team}"

    print(f"✅ Found {len(members)} team members: {', '.join(members)}")

    # Tag each member individually
    member_tags = " ".join([f"@{member}" for member in members])
    return member_tags


def create_approval_message(commenter: str, pr_numbers: str, member_tags: str, release_pr: Optional[str] = None) -> str:
    """
    Create the approval request message.

    Args:
        commenter: Username who requested the merge
        pr_numbers: Comma-separated PR numbers
        member_tags: String with team member tags
        release_pr: Optional release PR number

    Returns:
        Formatted approval request message
    """
    # Build release PR info if provided
    release_info = ""
    if release_pr and release_pr.strip():
        release_info = f"\n• **Release PR**: #{release_pr.strip()}"

    approval_message = f"""{member_tags} 🚀 **Merge Queue Approval Requested**

**Requested by**: @{commenter}
**PR Numbers**: {pr_numbers}{release_info}

**Action Required**: Please review the PRs and approve this merge queue request.

⏰ **Timeout**: This request will timeout in 60 minutes if not approved.
📋 **Reminders**: You'll receive reminders every 15 minutes.

**To approve**: React with 👍 to this comment or reply with 'approved'
**To reject**: React with 👎 to this comment or reply with 'rejected'

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

    # Get repository info to extract organization name
    try:
        repository = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
        org = repository.split('/')[0]
        print(f"Organization: {org}")
    except (ValueError, AttributeError):
        print("⚠️ GITHUB_REPOSITORY environment variable not set, cannot get team members")
        return False

    # Get team members for individual tagging
    member_tags = get_team_members_for_tagging(org, "merge-approvals")

    # Create the approval message
    approval_message = create_approval_message(commenter, pr_numbers, member_tags, release_pr)

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
