#!/usr/bin/env python3
"""
Check for duplicate merge queue runs and prevent conflicts.

This script checks for existing tracking issues to prevent duplicate
merge queue runs for the same original issue.
"""

import json
import sys
import os

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def find_existing_tracking_issue(original_issue_number: int) -> int | None:
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


def post_duplicate_message(original_issue_number: int, existing_tracking_issue: int) -> bool:
    """
    Post a duplicate prevention message to the original issue.

    Returns:
        True if message was posted successfully, False otherwise
    """
    duplicate_message = f"""⚠️ **Duplicate Merge Queue Request Detected**

A merge queue process is already running for this issue.

**Tracking Issue**: #{existing_tracking_issue}
**Action Required**: Wait for the current process to complete.

**Monitor Progress**: Check the tracking issue above for status updates.

**Retry**: Once the current process completes, you can comment `begin-merge` again if needed."""

    result = GitHubUtils.add_comment(str(original_issue_number), duplicate_message)
    if result.success:
        print("✅ Posted duplicate prevention message to original issue")
        return True
    else:
        print(f"⚠️ Failed to post duplicate message: {result.error_details}")
        return False


def main() -> int:
    """Main function to check for duplicate runs."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    print("🔒 Duplicate Run Prevention Check")
    print("=================================")
    print(f"Original Issue: #{issue_number}")
    print("=================================")

    existing_tracking_issue = find_existing_tracking_issue(issue_number)

    if existing_tracking_issue:
        print(f"❌ Duplicate run detected - tracking issue #{existing_tracking_issue} exists")
        print("This workflow run will be cancelled to prevent conflicts")
        
        # Post duplicate prevention message to original issue
        post_duplicate_message(issue_number, existing_tracking_issue)
        
        return 1

    print("✅ No duplicate run detected - proceeding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
