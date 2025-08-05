#!/usr/bin/env python3
"""
Trigger the merge queue workflow.

This script triggers the main merge queue workflow with the extracted
PR information and posts confirmation to the issue.
"""

import json
import os
import sys
from typing import Optional, Dict, Any

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def build_workflow_inputs(pr_numbers: str, release_pr: Optional[str] = None, required_approvals: Optional[str] = None) -> str:
    """
    Build the workflow inputs JSON string.
    
    Args:
        pr_numbers: Comma-separated PR numbers
        release_pr: Optional release PR number
        required_approvals: Optional required approvals override
    
    Returns:
        JSON string with workflow inputs
    """
    inputs: Dict[str, str] = {
        "pr_numbers": pr_numbers
    }
    
    # Add optional parameters if provided
    if release_pr and release_pr.strip():
        inputs["release_pr"] = release_pr.strip()
    
    if required_approvals and required_approvals.strip():
        inputs["required_approvals"] = required_approvals.strip()
    
    return json.dumps(inputs)


def trigger_workflow(workflow_inputs: str) -> bool:
    """
    Trigger the merge queue workflow.

    Args:
        workflow_inputs: JSON string with workflow inputs

    Returns:
        True if successful, False otherwise
    """
    print(f"Triggering merge queue workflow with inputs: {workflow_inputs}")

    # Use GitHubUtils to trigger the workflow
    result = GitHubUtils.trigger_workflow("merge_queue.yaml", workflow_inputs)

    if result.success:
        print("✅ Successfully triggered merge queue workflow")
        return True
    else:
        print(f"❌ Failed to trigger workflow: {result.stderr}")
        return False


def post_confirmation_message(issue_number: int, approver: str, pr_numbers: str, 
                            release_pr: Optional[str], repository: str) -> bool:
    """
    Post confirmation message to the issue.
    
    Args:
        issue_number: Issue number to comment on
        approver: Username who approved the request
        pr_numbers: Comma-separated PR numbers
        release_pr: Optional release PR number
        repository: Repository name (owner/repo)
    
    Returns:
        True if successful, False otherwise
    """
    print(f"Posting confirmation message to issue #{issue_number}...")
    
    # Build release PR info if provided
    release_info = f"\n**Release PR**: {release_pr}" if release_pr and release_pr.strip() else "\n**Release PR**: None"
    
    confirmation_message = f"""🚀 **Merge Queue Started**

**Approved by**: @{approver}
**PR Numbers**: {pr_numbers}{release_info}

The merge queue workflow has been triggered successfully.

📊 **Monitor Progress**: [View Workflow Run](https://github.com/{repository}/actions)
🔔 **Notifications**: PR creators will receive immediate notifications for any issues

*This issue will be automatically updated with the final results.*"""
    
    result = GitHubUtils.comment_on_pr(str(issue_number), confirmation_message)
    
    if result.success:
        print("✅ Successfully posted confirmation message")
        return True
    else:
        print(f"❌ Failed to post confirmation message: {result.error_details}")
        return False


def main() -> int:
    """Main function to trigger merge queue workflow."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    approver: str = GitHubUtils.get_env_var("APPROVER")
    pr_numbers: str = GitHubUtils.get_env_var("PR_NUMBERS")
    release_pr: str = GitHubUtils.get_env_var("RELEASE_PR", "")
    required_approvals: str = GitHubUtils.get_env_var("REQUIRED_APPROVALS", "")
    repository: str = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    # Validate required parameters
    if not approver:
        print("❌ Missing approver information")
        return 1
    
    if not pr_numbers:
        print("❌ Missing PR numbers")
        return 1
    
    if not repository:
        print("❌ Missing repository information")
        return 1
    
    print("=== Merge Queue Workflow Trigger ===")
    print(f"Issue: #{issue_number}")
    print(f"Approver: @{approver}")
    print(f"PR Numbers: {pr_numbers}")
    print(f"Release PR: {release_pr if release_pr else '(none)'}")
    print(f"Required Approvals: {required_approvals if required_approvals else '(none)'}")
    print(f"Repository: {repository}")
    print("====================================")
    
    # Build workflow inputs
    workflow_inputs = build_workflow_inputs(pr_numbers, release_pr, required_approvals)
    print(f"Workflow inputs: {workflow_inputs}")
    
    # Trigger the workflow
    workflow_success = trigger_workflow(workflow_inputs)
    if not workflow_success:
        print("❌ Failed to trigger merge queue workflow")
        return 1
    
    # Post confirmation message
    confirmation_success = post_confirmation_message(
        issue_number, approver, pr_numbers, release_pr, repository
    )
    if not confirmation_success:
        print("⚠️ Workflow triggered but failed to post confirmation message")
        # Don't fail the step for this - workflow was triggered successfully
    
    print("✅ Merge queue workflow trigger completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
