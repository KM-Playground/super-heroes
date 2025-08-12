#!/usr/bin/env python3
"""
Wait for approval from merge-approvals team with reminders.

This script handles the approval waiting logic for merge queue requests,
including team membership validation and reminder notifications.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils

# Global sets to track unauthorized comments we've already warned about
warned_unauthorized_approvals = set()
warned_unauthorized_rejections = set()


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime object."""
    if not timestamp_str or timestamp_str.strip() == "":
        return None

    try:
        # Handle both with and without microseconds
        if '.' in timestamp_str:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError as e:
        print(f"⚠️ Error parsing timestamp '{timestamp_str}': {e}")
        return None


def get_comments_after_timestamp(issue_number: int, trigger_timestamp: str) -> List[Dict[str, Any]]:
    """Get all comments on the issue that were created after the trigger timestamp."""
    result = GitHubUtils.get_all_comments(str(issue_number))

    if not result.success:
        print(f"❌ Failed to get comments: {result.stderr}")
        return []

    try:
        data = json.loads(result.stdout)
        comments: List[Dict[str, Any]] = data.get("comments", [])

        # Parse trigger timestamp
        trigger_dt = parse_iso_timestamp(trigger_timestamp)
        if not trigger_dt:
            print(f"❌ Invalid trigger timestamp: {trigger_timestamp}")
            return []

        # Filter comments after trigger time
        filtered_comments: List[Dict[str, Any]] = []
        for comment in comments:
            created_at = comment.get("createdAt")  # GitHub CLI uses camelCase
            if not created_at:
                print(f"⚠️ Comment missing createdAt timestamp, skipping: {comment.get('id', 'unknown')}")
                continue

            comment_dt = parse_iso_timestamp(created_at)
            if comment_dt and comment_dt > trigger_dt:
                # Skip bot comments
                author = comment.get("author", {}).get("login", "")
                if author != "github-actions[bot]":
                    filtered_comments.append(comment)

        return filtered_comments

    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error parsing comments: {e}")
        return []


def get_team_members_from_env() -> List[str]:
    """
    Get list of team members from environment variables set by workflow.

    Returns:
        List of team member usernames, empty if not available
    """
    team_members_str = GitHubUtils.get_env_var("TEAM_MEMBERS", "")

    if team_members_str:
        # Split the space-separated list of members
        members = [member.strip() for member in team_members_str.split() if member.strip()]
        print(f"✅ Team members from workflow: {', '.join(members)}")
        return members
    else:
        print(f"⚠️ No team members available from workflow")
        print(f"   Approval validation will be skipped")
        return []


def check_for_approval_or_rejection(issue_number: int, trigger_timestamp: str, org: str) -> Tuple[Optional[str], Optional[str]]:
    """Check for approval or rejection comments after the trigger timestamp."""
    comments = get_comments_after_timestamp(issue_number, trigger_timestamp)

    # Get team members list for validation from environment
    team_members = get_team_members_from_env()

    approval_keywords: List[str] = ["approved", "👍"]
    rejection_keywords: List[str] = ["rejected", "👎"]

    for comment in comments:
        author: str = comment.get("author", {}).get("login", "")
        body: str = comment.get("body", "").lower()

        # Skip comments from github-actions to avoid detecting our own confirmation messages as approvals
        if author == "github-actions":
            print(f"Skipping comment from github-actions (automated system comment)")
            continue

        # Check for approval
        if any(keyword in body for keyword in approval_keywords):
            print(f"Found approval comment from: {author}")

            # Verify team membership using the retrieved team members list
            if team_members and author in team_members:
                print(f"✅ Approval from authorized team member: {author}")
                return "approved", author
            elif team_members:
                print(f"⚠️ Approval from unauthorized user: {author} (not in team: {', '.join(team_members)})")

                # Create a unique identifier for this comment to avoid duplicate warnings
                comment_id = comment.get("id", "")
                comment_key = f"{author}_{comment_id}"

                # Only post warning if we haven't already warned about this comment
                if comment_key not in warned_unauthorized_approvals:
                    warning_message: str = f"""⚠️ **Unauthorized Approval Attempt**

@{author} attempted to approve this request, but is not a member of the `merge-approvals` team.

**Required**: Approval must come from a member of the `merge-approvals` team.
**Current team members**: {', '.join([f'@{member}' for member in team_members])}"""

                    result = GitHubUtils.add_comment(str(issue_number), warning_message)
                    if result.success:
                        warned_unauthorized_approvals.add(comment_key)
                        print(f"✅ Posted warning for unauthorized approval from {author}")
                    else:
                        print(f"⚠️ Failed to post warning comment: {result.error_details}")
                else:
                    print(f"⚠️ Already warned about unauthorized approval from {author} (comment {comment_id})")
            else:
                # Fallback to API check if we couldn't get team members list
                print(f"⚠️ Could not retrieve team members, falling back to API check")
                if GitHubUtils.is_team_member(author, org, "merge-approvals"):
                    print(f"✅ Approval from authorized team member: {author}")
                    return "approved", author
                else:
                    print(f"⚠️ Approval from unauthorized user: {author}")

                    # Create a unique identifier for this comment to avoid duplicate warnings
                    comment_id = comment.get("id", "")
                    comment_key = f"{author}_{comment_id}"

                    # Only post warning if we haven't already warned about this comment
                    if comment_key not in warned_unauthorized_approvals:
                        warning_message: str = f"""⚠️ **Unauthorized Approval Attempt**

@{author} attempted to approve this request, but is not a member of the `merge-approvals` team.

**Required**: Approval must come from a member of the `merge-approvals` team."""

                        result = GitHubUtils.add_comment(str(issue_number), warning_message)
                        if result.success:
                            warned_unauthorized_approvals.add(comment_key)
                            print(f"✅ Posted warning for unauthorized approval from {author}")
                        else:
                            print(f"⚠️ Failed to post warning comment: {result.error_details}")
                    else:
                        print(f"⚠️ Already warned about unauthorized approval from {author} (comment {comment_id})")

        # Check for rejection
        elif any(keyword in body for keyword in rejection_keywords):
            print(f"Found rejection comment from: {author}")

            # Verify team membership using the retrieved team members list
            if team_members and author in team_members:
                print(f"❌ Rejection from authorized team member: {author}")
                return "rejected", author
            elif team_members:
                print(f"⚠️ Rejection from unauthorized user: {author} (not in team: {', '.join(team_members)})")

                # Create a unique identifier for this comment to avoid duplicate warnings
                comment_id = comment.get("id", "")
                comment_key = f"{author}_{comment_id}"

                # Only post warning if we haven't already warned about this comment
                if comment_key not in warned_unauthorized_rejections:
                    warning_message: str = f"""⚠️ **Unauthorized Rejection Attempt**

@{author} attempted to reject this request, but is not a member of the `merge-approvals` team.

**Required**: Rejection must come from a member of the `merge-approvals` team.
**Current team members**: {', '.join([f'@{member}' for member in team_members])}"""

                    result = GitHubUtils.add_comment(str(issue_number), warning_message)
                    if result.success:
                        warned_unauthorized_rejections.add(comment_key)
                        print(f"✅ Posted warning for unauthorized rejection from {author}")
                    else:
                        print(f"⚠️ Failed to post warning comment: {result.error_details}")
                else:
                    print(f"⚠️ Already warned about unauthorized rejection from {author} (comment {comment_id})")
            else:
                # Fallback to API check if we couldn't get team members list
                print(f"⚠️ Could not retrieve team members, falling back to API check")
                if GitHubUtils.is_team_member(author, org, "merge-approvals"):
                    print(f"❌ Rejection from authorized team member: {author}")
                    return "rejected", author
                else:
                    print(f"⚠️ Rejection from unauthorized user: {author}")

                    # Create a unique identifier for this comment to avoid duplicate warnings
                    comment_id = comment.get("id", "")
                    comment_key = f"{author}_{comment_id}"

                    # Only post warning if we haven't already warned about this comment
                    if comment_key not in warned_unauthorized_rejections:
                        warning_message: str = f"""⚠️ **Unauthorized Rejection Attempt**

@{author} attempted to reject this request, but is not a member of the `merge-approvals` team.

**Required**: Rejection must come from a member of the `merge-approvals` team."""

                        result = GitHubUtils.add_comment(str(issue_number), warning_message)
                        if result.success:
                            warned_unauthorized_rejections.add(comment_key)
                            print(f"✅ Posted warning for unauthorized rejection from {author}")
                        else:
                            print(f"⚠️ Failed to post warning comment: {result.error_details}")
                    else:
                        print(f"⚠️ Already warned about unauthorized rejection from {author} (comment {comment_id})")

    return None, None


def send_reminder(issue_number: int, remaining_minutes: int) -> None:
    """Send a reminder comment to the issue."""
    # Get team tag from environment variables (set by workflow)
    team_tag = GitHubUtils.get_env_var("TEAM_TAG", "")

    if team_tag:
        member_tags = team_tag
        print(f"📧 Using team tag from workflow for reminder: {member_tags}")
    else:
        # Fallback if environment variables not set
        try:
            repository = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
            org = repository.split('/')[0]
            member_tags = f"@{org}/merge-approvals"
            print(f"⚠️ Using fallback team tag for reminder: {member_tags}")
        except (ValueError, AttributeError):
            member_tags = "@merge-approvals"
            print(f"⚠️ Using generic fallback for reminder: {member_tags}")

    reminder_message: str = f"""⏰ **Reminder**: Merge queue approval still pending

{member_tags} - Please review and approve this merge request.

**Time remaining**: {remaining_minutes} minutes
**To approve**: Reply with 'approved'
**To reject**: Reply with 'rejected'"""

    result = GitHubUtils.add_comment(str(issue_number), reminder_message)
    if result.success:
        print(f"✅ Sent reminder - {remaining_minutes} minutes remaining")
    else:
        print(f"⚠️ Failed to send reminder: {result.error_details}")


def send_timeout_message(issue_number: int, timeout_minutes: int) -> None:
    """Send timeout message to the issue."""
    timeout_message: str = f"""⏰ **Approval Timeout**

No approval was received within {timeout_minutes} minutes. The merge queue request has timed out.

**To restart**: Comment `begin-merge` again to start a new approval process."""

    result = GitHubUtils.add_comment(str(issue_number), timeout_message)
    if result.success:
        print("✅ Sent timeout message")
    else:
        print(f"⚠️ Failed to send timeout message: {result.error_details}")


def send_approval_confirmation(issue_number: int, approver: str, repository: str) -> None:
    """Send approval confirmation message."""
    # Get workflow run information for direct link
    server_url = GitHubUtils.get_env_var("GITHUB_SERVER_URL", "https://github.com")
    run_id = GitHubUtils.get_env_var("GITHUB_RUN_ID", "")

    # Build workflow run URL if we have the run ID
    if run_id:
        workflow_url = f"{server_url}/{repository}/actions/runs/{run_id}"
        progress_link = f"[View workflow progress]({workflow_url})"
    else:
        # Fallback to general Actions tab
        progress_link = f"[Actions tab](https://github.com/{repository}/actions)"

    confirmation_message: str = f"""✅ **Approved by @{approver}**

✅ **Authorization Verified**: Member of `merge-approvals` team

The merge queue workflow will now execute automatically.

Monitor the progress: {progress_link}"""

    result = GitHubUtils.add_comment(str(issue_number), confirmation_message)
    if result.success:
        print(f"✅ Sent approval confirmation for @{approver}")
    else:
        print(f"⚠️ Failed to send approval confirmation: {result.error_details}")


def send_rejection_confirmation(issue_number: int, rejector: str) -> None:
    """Send rejection confirmation message."""
    rejection_message: str = f"""❌ **Rejected by @{rejector}**

✅ **Authorization Verified**: Member of `merge-approvals` team

The merge queue request has been rejected. Please address any concerns and comment `begin-merge` again to restart the process."""

    result = GitHubUtils.add_comment(str(issue_number), rejection_message)
    if result.success:
        print(f"✅ Sent rejection confirmation for @{rejector}")
    else:
        print(f"⚠️ Failed to send rejection confirmation: {result.error_details}")


def main() -> int:
    """Main function to wait for approval with reminders."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    trigger_timestamp: str = GitHubUtils.get_env_var("TRIGGER_COMMENT_TIME")
    repository: str = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
    org: str = repository.split('/')[0]

    # Get configurable timeout and reminder interval values
    timeout_minutes_str: str = GitHubUtils.get_env_var("APPROVAL_TIMEOUT_MINUTES", "60")
    reminder_interval_str: str = GitHubUtils.get_env_var("APPROVAL_REMINDER_INTERVAL_MINUTES", "15")

    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1

    # Convert timeout and reminder interval to int with validation
    try:
        timeout_minutes: int = int(timeout_minutes_str)
        if timeout_minutes <= 0:
            print(f"⚠️ Invalid timeout value '{timeout_minutes_str}', using default: 60")
            timeout_minutes = 60
    except ValueError:
        print(f"⚠️ Invalid timeout value '{timeout_minutes_str}', using default: 60")
        timeout_minutes = 60

    try:
        reminder_interval: int = int(reminder_interval_str)
        if reminder_interval <= 0:
            print(f"⚠️ Invalid reminder interval '{reminder_interval_str}', using default: 15")
            reminder_interval = 15
    except ValueError:
        print(f"⚠️ Invalid reminder interval '{reminder_interval_str}', using default: 15")
        reminder_interval = 15

    print("=== Waiting for Approval ===")
    print(f"Issue: #{issue_number}")
    print(f"Trigger timestamp: {trigger_timestamp}")
    print(f"Repository: {repository}")
    print(f"Organization: {org}")
    print(f"Timeout: {timeout_minutes} minutes")
    print(f"Reminder interval: {reminder_interval} minutes")
    print("============================")

    elapsed_minutes: int = 0
    
    while elapsed_minutes < timeout_minutes:
        print(f"Checking for approval... ({elapsed_minutes}/{timeout_minutes} minutes elapsed)")
        
        # Check for approval or rejection
        status, user = check_for_approval_or_rejection(issue_number, trigger_timestamp, org)

        if status == "approved" and user:
            send_approval_confirmation(issue_number, user, repository)
            # Set outputs for GitHub Actions
            github_output: Optional[str] = os.environ.get('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write(f"approved=true\n")
                    f.write(f"approver={user}\n")
            return 0
        elif status == "rejected" and user:
            send_rejection_confirmation(issue_number, user)
            # Set outputs for GitHub Actions
            github_output = os.environ.get('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write(f"approved=false\n")
                    f.write(f"rejection_reason=rejected\n")
            return 1

        # Send reminder every 15 minutes
        if elapsed_minutes > 0 and elapsed_minutes % reminder_interval == 0:
            remaining_minutes: int = timeout_minutes - elapsed_minutes
            send_reminder(issue_number, remaining_minutes)

        # Wait 1 minute before next check
        time.sleep(60)
        elapsed_minutes += 1

    # Timeout reached
    print("⏰ Approval timeout reached")
    send_timeout_message(issue_number, timeout_minutes)
    # Set outputs for GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"approved=false\n")
            f.write(f"rejection_reason=timeout\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
