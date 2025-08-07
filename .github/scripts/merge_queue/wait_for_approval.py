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


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime object."""
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
            comment_dt = parse_iso_timestamp(comment.get("created_at", ""))
            if comment_dt and comment_dt > trigger_dt:
                # Skip bot comments
                author = comment.get("author", {}).get("login", "")
                if author != "github-actions[bot]":
                    filtered_comments.append(comment)

        return filtered_comments

    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error parsing comments: {e}")
        return []


def check_for_approval_or_rejection(issue_number: int, trigger_timestamp: str, org: str) -> Tuple[Optional[str], Optional[str]]:
    """Check for approval or rejection comments after the trigger timestamp."""
    comments = get_comments_after_timestamp(issue_number, trigger_timestamp)

    approval_keywords: List[str] = ["approved", "👍"]
    rejection_keywords: List[str] = ["rejected", "👎"]

    for comment in comments:
        author: str = comment.get("author", {}).get("login", "")
        body: str = comment.get("body", "").lower()

        # Check for approval
        if any(keyword in body for keyword in approval_keywords):
            print(f"Found approval comment from: {author}")

            # Verify team membership
            if GitHubUtils.is_team_member(author, org, "merge-approvals"):
                print(f"✅ Approval from authorized team member: {author}")
                return "approved", author
            else:
                print(f"⚠️ Approval from unauthorized user: {author}")
                # Post warning but continue checking
                warning_message: str = f"""⚠️ **Unauthorized Approval Attempt**

@{author} attempted to approve this request, but is not a member of the `merge-approvals` team.

**Required**: Approval must come from a member of the `merge-approvals` team."""

                result = GitHubUtils.add_comment(str(issue_number), warning_message)
                if not result.success:
                    print(f"⚠️ Failed to post warning comment: {result.error_details}")

        # Check for rejection
        elif any(keyword in body for keyword in rejection_keywords):
            print(f"Found rejection comment from: {author}")

            # Verify team membership
            if GitHubUtils.is_team_member(author, org, "merge-approvals"):
                print(f"❌ Rejection from authorized team member: {author}")
                return "rejected", author
            else:
                print(f"⚠️ Rejection from unauthorized user: {author}")
                # Post warning but continue checking
                warning_message: str = f"""⚠️ **Unauthorized Rejection Attempt**

@{author} attempted to reject this request, but is not a member of the `merge-approvals` team.

**Required**: Rejection must come from a member of the `merge-approvals` team."""

                result = GitHubUtils.add_comment(str(issue_number), warning_message)
                if not result.success:
                    print(f"⚠️ Failed to post warning comment: {result.error_details}")

    return None, None


def send_reminder(issue_number: int, remaining_minutes: int) -> None:
    """Send a reminder comment to the issue."""
    reminder_message: str = f"""⏰ **Reminder**: Merge queue approval still pending

@merge-approvals - Please review and approve this merge request.

**Time remaining**: {remaining_minutes} minutes
**To approve**: React with 👍 or reply with 'approved'
**To reject**: React with 👎 or reply with 'rejected'"""

    result = GitHubUtils.add_comment(str(issue_number), reminder_message)
    if result.success:
        print(f"✅ Sent reminder - {remaining_minutes} minutes remaining")
    else:
        print(f"⚠️ Failed to send reminder: {result.error_details}")


def send_timeout_message(issue_number: int) -> None:
    """Send timeout message to the issue."""
    timeout_message: str = """⏰ **Approval Timeout**

No approval was received within 60 minutes. The merge queue request has timed out.

**To restart**: Comment `begin-merge` again to start a new approval process."""

    result = GitHubUtils.add_comment(str(issue_number), timeout_message)
    if result.success:
        print("✅ Sent timeout message")
    else:
        print(f"⚠️ Failed to send timeout message: {result.error_details}")


def send_approval_confirmation(issue_number: int, approver: str, repository: str) -> None:
    """Send approval confirmation message."""
    confirmation_message: str = f"""✅ **Approved by @{approver}**

✅ **Authorization Verified**: Member of `merge-approvals` team

The merge queue workflow will now execute automatically.

Monitor the progress in the [Actions tab](https://github.com/{repository}/actions)."""

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

    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1

    print("=== Waiting for Approval ===")
    print(f"Issue: #{issue_number}")
    print(f"Trigger timestamp: {trigger_timestamp}")
    print(f"Repository: {repository}")
    print(f"Organization: {org}")
    print("============================")

    timeout_minutes: int = 60
    reminder_interval: int = 15
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
    send_timeout_message(issue_number)
    # Set outputs for GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"approved=false\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
