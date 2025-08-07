#!/usr/bin/env python3
"""
Check for consecutive execution prevention.

This script checks if there are already running merge queue workflows
to prevent multiple concurrent executions.
"""

import json
import os
import sys
from typing import List, Dict, Any

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def get_running_workflows(workflow_name: str) -> List[Dict[str, Any]]:
    """Get list of running workflows for a specific workflow file."""
    result = GitHubUtils.get_running_workflows(workflow_name)

    if not result.success:
        print(f"❌ Failed to get running workflows for {workflow_name}: {result.stderr}")
        return []

    try:
        workflows: List[Dict[str, Any]] = json.loads(result.stdout)
        return workflows
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing workflow data: {e}")
        return []


def check_consecutive_execution(issue_number: int, repository: str) -> bool:
    """
    Check if there are conflicting workflow runs that would prevent execution.

    Returns:
        True if execution should proceed (no conflicts)
        False if execution should be blocked (conflicts found)
    """
    print("Checking for existing merge queue workflow runs...")

    # Get current workflow filename from GitHub Actions environment
    # GITHUB_WORKFLOW_REF format: "owner/repo/.github/workflows/workflow.yml@refs/heads/branch"
    workflow_ref = GitHubUtils.get_env_var("GITHUB_WORKFLOW_REF", "")
    workflow_filename = "merge_queue.yaml"
    if workflow_ref:
        # Extract filename from the workflow reference
        # Split by '/' and get the second-to-last element (which contains "filename@refs/heads")
        # Then split by '@' to get just the filename
        parts = workflow_ref.split('/')
        if len(parts) >= 2:
            workflow_filename = parts[-2].split('@')[0]  # Get "workflow.yml" from "workflow.yml@refs/heads"
            print(f"Detected current workflow: {workflow_filename}")
        else:
            print(f"Could not parse workflow reference '{workflow_ref}', using fallback: {workflow_filename}")
    else:
        # Fallback to hardcoded name if environment variable is not available
        print(f"Using fallback workflow name: {workflow_filename}")

    # Check for running merge queue workflows (now unified into single workflow)
    running_merge = get_running_workflows(workflow_filename)

    merge_count = len(running_merge)

    print(f"Running merge queue workflows: {merge_count}")

    # Allow current workflow (1 merge queue workflow is expected - this one)
    # Block if there are more than 1 merge queue workflows running
    if merge_count > 1:
        print("❌ Consecutive execution prevented - existing workflow runs found")

        # Build detailed message about active workflows
        active_workflows = [f"• Merge Queue workflows: {merge_count}"]
        active_workflows_text = "\n".join(active_workflows)

        # Post blocking message to the issue
        blocking_message = f"""⚠️ **Consecutive Execution Prevented**

There are already active merge queue workflows running:
{active_workflows_text}

**Action Required**: Wait for the current workflows to complete before starting a new merge queue process.

**Monitor Progress**: [View Active Workflows](https://github.com/{repository}/actions)

**Retry**: Comment `begin-merge` again once all workflows have completed."""

        result = GitHubUtils.comment_on_pr(str(issue_number), blocking_message)
        if result.success:
            print("✅ Posted consecutive execution prevention message")
        else:
            print(f"⚠️ Failed to post blocking message: {result.error_details}")

        return False

    print("✅ No conflicting workflow runs found - proceeding with new request")
    return True


def main() -> int:
    """Main function to check for consecutive execution."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    repository: str = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    print("=== Consecutive Execution Check ===")
    print(f"Issue: #{issue_number}")
    print(f"Repository: {repository}")
    print("===================================")
    
    # Check for consecutive execution
    can_proceed = check_consecutive_execution(issue_number, repository)
    
    if can_proceed:
        print("✅ Execution check passed - proceeding")
        return 0
    else:
        print("❌ Execution check failed - blocking")
        return 1


if __name__ == "__main__":
    sys.exit(main())
