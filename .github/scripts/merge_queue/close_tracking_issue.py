#!/usr/bin/env python3
"""
Close Merge Queue Tracking Issue.

This script closes the tracking issue when the merge queue process completes,
regardless of the outcome (success, failure, timeout, rejection).
"""

import json
import sys
import os
from typing import Optional

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def find_existing_tracking_issue(original_issue_number: int) -> Optional[int]:
    """
    Find an existing tracking issue for the given original issue number.

    Returns:
        The tracking issue number if found, None otherwise
    """
    print(f"Searching for existing tracking issue for original issue #{original_issue_number}...")

    # Use label-based filtering for efficient searching
    # Only look at issues with the "distributed-lock" label
    title_pattern = f"[MERGE QUEUE TRACKING] Issue #{original_issue_number}"

    result = GitHubUtils.list_issues(
        state="open",
        label="distributed-lock",
        limit=50  # Should be more than enough for active locks
    )

    if not result.success:
        print(f"⚠️ Failed to list distributed-lock issues: {result.error_details}")
        return None

    try:
        issues = json.loads(result.stdout)

        for issue in issues:
            title = issue.get("title", "")
            if title.startswith(title_pattern):
                issue_number = issue.get("number")
                print(f"✅ Found existing tracking issue: #{issue_number}")
                return issue_number

        print("✅ No existing tracking issue found")
        return None

    except json.JSONDecodeError as e:
        print(f"❌ Error parsing distributed-lock issue list: {e}")
        return None


def close_tracking_issue(tracking_issue_number: int, completion_status: str, summary_message: str = "") -> bool:
    """
    Close a tracking issue with a completion message.

    Args:
        tracking_issue_number: The tracking issue number to close
        completion_status: Status like "completed", "rejected", "timeout", "failed"
        summary_message: Optional summary message to add

    Returns:
        True if closed successfully, False otherwise
    """
    print(f"Closing tracking issue #{tracking_issue_number} with status: {completion_status}")

    # Add completion comment
    status_emoji = {
        "completed": "✅",
        "rejected": "❌",
        "timeout": "⏰",
        "failed": "💥"
    }.get(completion_status, "🔄")

    completion_comment = f"""{status_emoji} **Merge Queue Process {completion_status.title()}**

The merge queue process has {completion_status}.

{summary_message}

This tracking issue is now being closed automatically."""

    # Add comment
    comment_result = GitHubUtils.add_comment(str(tracking_issue_number), completion_comment)
    if not comment_result.success:
        print(f"⚠️ Failed to add completion comment: {comment_result.error_details}")

    # Close the issue
    close_result = GitHubUtils.close_issue(tracking_issue_number)

    if close_result.success:
        print(f"✅ Successfully closed tracking issue #{tracking_issue_number}")
        return True
    else:
        print(f"❌ Failed to close tracking issue: {close_result.error_details}")
        return False


def main() -> int:
    """Main function to close tracking issue."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    repository: str = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
    
    # Get completion status and summary from environment or arguments
    completion_status: str = GitHubUtils.get_env_var("COMPLETION_STATUS", "completed")
    summary_message: str = GitHubUtils.get_env_var("SUMMARY_MESSAGE", "")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    print("=== Merge Queue Tracking Closure ===")
    print(f"Original Issue: #{issue_number}")
    print(f"Repository: {repository}")
    print(f"Status: {completion_status}")
    print("===================================")
    
    # Try to get tracking issue number from properties file first
    tracking_issue_number = None
    try:
        if os.path.exists("/tmp/tracking_issue.properties"):
            with open("/tmp/tracking_issue.properties", "r") as f:
                for line in f:
                    if line.startswith("TRACKING_ISSUE_NUMBER="):
                        tracking_issue_number = int(line.split("=")[1].strip())
                        break
    except (ValueError, FileNotFoundError):
        pass
    
    # If not found in properties file, search for it
    if not tracking_issue_number:
        print("Tracking issue number not found in properties, searching...")
        tracking_issue_number = find_existing_tracking_issue(issue_number)
    
    if not tracking_issue_number:
        print("⚠️ No tracking issue found to close")
        return 0  # Not an error - maybe tracking issue was already closed
    
    # Close the tracking issue
    success = close_tracking_issue(tracking_issue_number, completion_status, summary_message)
    
    if success:
        print(f"✅ Successfully closed tracking issue #{tracking_issue_number}")
        return 0
    else:
        print(f"❌ Failed to close tracking issue #{tracking_issue_number}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
