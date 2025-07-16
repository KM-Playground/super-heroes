#!/usr/bin/env python3
"""
Merge PRs sequentially in chronological order.

This script handles the complete merge process:
1. Sort PRs by number (chronological order)
2. Update each PR with the default branch
3. Trigger CI by commenting "ok to test"
4. Wait for CI to complete
5. Merge the PR if all checks pass
6. Track results and failures
"""

import os
import json
import sys
import time
from typing import List, Tuple

from gh_utils import get_env_var, run_gh_command


def parse_mergeable_prs(json_str: str) -> List[int]:
    """Parse and sort mergeable PRs from JSON string."""
    if not json_str or json_str.strip() == "":
        return []
    
    try:
        pr_strings = json.loads(json_str)
        pr_numbers = [int(pr) for pr in pr_strings]
        return sorted(pr_numbers)  # Sort chronologically (lowest number first)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing mergeable PRs: {e}")
        return []


def update_pr_branch(pr_number: int, default_branch: str) -> bool:
    """Update PR branch with the default branch."""
    print(f"Updating PR #{pr_number} with {default_branch} branch...")
    success, stdout, stderr = run_gh_command(["pr", "update-branch", str(pr_number)], check=False)
    
    if not success:
        print(f"⚠️ Failed to update PR #{pr_number} with {default_branch}")
        if stderr:
            print(f"Error: {stderr}")
        return False
    
    print(f"✅ Successfully updated PR #{pr_number}")
    return True


def trigger_ci(pr_number: int) -> bool:
    """Trigger CI by commenting 'ok to test' on the PR."""
    print(f"Triggering CI for PR #{pr_number}...")
    success, stdout, stderr = run_gh_command(["pr", "comment", str(pr_number), "--body", "Ok to test"], check=False)

    if not success:
        print(f"⚠️ Failed to trigger CI for PR #{pr_number}")
        if stderr:
            print(f"Error: {stderr}")
        return False

    print(f"✅ CI triggered for PR #{pr_number}")
    return True


def wait_for_ci_to_start(pr_number: int, max_startup_wait: int = 300, required_check: str = "run-tests") -> bool:
    """
    Wait for CI workflow to start and register status checks.

    Args:
        pr_number: The PR number to monitor
        max_startup_wait: Maximum seconds to wait for CI to start (default: 5 minutes)
        required_check: The name of the required CI check context (default: "run-tests")

    Returns:
        True if CI started (status checks detected), False if timeout
    """
    print(f"⏳ Waiting for CI workflow to start for PR #{pr_number}...")
    print(f"Looking for required CI check: '{required_check}'")

    wait_time = 0
    check_intervals = [5, 5, 10, 10, 15, 15, 30, 30]  # Progressive intervals
    interval_index = 0

    while wait_time < max_startup_wait:
        # Get current interval, using the last one if we've exceeded the list
        current_interval = check_intervals[min(interval_index, len(check_intervals) - 1)]

        # Check for status checks (but don't print detailed debug info yet)
        success, stdout, stderr = run_gh_command(["pr", "view", str(pr_number), "--json", "statusCheckRollup"], check=False)

        if success:
            try:
                status_info = json.loads(stdout)
                checks = status_info.get("statusCheckRollup", [])

                # Look for our specific required check
                found_required_check = False
                for check in checks:
                    context = check.get("context", "")
                    if required_check in context:
                        found_required_check = True
                        print(f"✅ Found required CI check '{required_check}' for PR #{pr_number}")
                        break

                if found_required_check:
                    print(f"✅ CI workflow started for PR #{pr_number} (detected required check '{required_check}')")
                    return True
                elif checks:
                    # We have some checks but not the one we're waiting for
                    check_names = [check.get("context", "unknown") for check in checks]
                    print(f"⏳ Found {len(checks)} check(s) but not '{required_check}' yet: {', '.join(check_names)}")

            except (json.JSONDecodeError, KeyError):
                pass  # Continue waiting

        print(f"⏳ CI not started yet for PR #{pr_number}, waiting {current_interval}s... ({wait_time}/{max_startup_wait}s elapsed)")
        time.sleep(current_interval)
        wait_time += current_interval
        interval_index += 1

    print(f"⚠️ Timeout waiting for CI to start for PR #{pr_number} after {max_startup_wait}s")
    return False


def get_pr_status_checks(pr_number: int, required_check: str = "run-tests") -> Tuple[int, int]:
    """Get the count of pending and failed status checks for a PR."""
    success, stdout, stderr = run_gh_command(["pr", "view", str(pr_number), "--json", "statusCheckRollup"], check=False)

    if not success:
        print(f"⚠️ Failed to get status checks for PR #{pr_number}")
        return 0, 1  # Assume failure if we can't get status

    try:
        status_info = json.loads(stdout)
        checks = status_info.get("statusCheckRollup", [])

        # Debug: Show all status checks
        print(f"📊 Status checks for PR #{pr_number}:")
        if not checks:
            print("  No status checks found")
        else:
            for check in checks:
                context = check.get("context", "unknown")
                state = check.get("state", "unknown")
                description = check.get("description", "")
                print(f"  - {context}: {state} ({description})")

        pending_count = sum(1 for check in checks if check.get("state") in ["PENDING", "IN_PROGRESS"])
        failed_count = sum(1 for check in checks if check.get("state") in ["FAILURE", "ERROR"])
        success_count = sum(1 for check in checks if check.get("state") == "SUCCESS")

        print(f"📈 Summary: {pending_count} pending, {failed_count} failed, {success_count} passed")

        # If no checks exist at all, we should treat this as "pending" until CI starts
        if not checks:
            print("⚠️ No status checks found - treating as pending until CI registers")
            return 1, 0  # Return 1 pending to indicate we're still waiting

        # Check if we have the specific required check
        has_required_check = any(required_check in check.get("context", "") for check in checks)

        if not has_required_check:
            print(f"⚠️ Required check '{required_check}' not found - treating as pending")
            return 1, 0  # Return 1 pending to indicate we're still waiting for the right check

        return pending_count, failed_count
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ Error parsing status checks for PR #{pr_number}: {e}")
        return 0, 1  # Assume failure if we can't parse


def wait_for_ci(pr_number: int, max_wait_seconds: int = 2700, check_interval: int = 30, max_startup_wait: int = 300, required_check: str = "run-tests") -> str:
    """
    Wait for CI to complete on a PR.

    Args:
        pr_number: The PR number to monitor
        max_wait_seconds: Maximum seconds to wait for CI completion (default: 45 minutes)
        check_interval: Seconds between status checks during CI execution (default: 30s)
        max_startup_wait: Maximum seconds to wait for CI to start (default: 5 minutes)
        required_check: The name of the required CI check context (default: "run-tests")

    Returns:
        "success" - All checks passed
        "failed" - Some checks failed
        "timeout" - Timed out waiting for checks
        "startup_timeout" - CI never started
    """
    # First, wait for CI to start
    if not wait_for_ci_to_start(pr_number, max_startup_wait, required_check):
        return "startup_timeout"

    print(f"🔄 Monitoring CI execution for PR #{pr_number}...")
    wait_time = 0

    while wait_time < max_wait_seconds:
        pending_checks, failed_checks = get_pr_status_checks(pr_number, required_check)

        if pending_checks == 0:
            if failed_checks == 0:
                print(f"✅ All CI checks passed for PR #{pr_number}")
                return "success"
            else:
                print(f"❌ CI checks failed for PR #{pr_number}, skipping merge")
                return "failed"

        print(f"⏳ CI still running for PR #{pr_number}... waiting {check_interval}s ({wait_time}/{max_wait_seconds}s elapsed)")
        time.sleep(check_interval)
        wait_time += check_interval

    print(f"⏰ Timeout waiting for CI completion on PR #{pr_number}, skipping merge")
    return "timeout"


def is_release_branch(pr_number: int) -> bool:
    """Check if a PR is from a release branch."""
    success, stdout, stderr = run_gh_command(["pr", "view", str(pr_number), "--json", "headRefName"], check=False)
    if not success:
        print(f"⚠️ Could not determine branch name for PR #{pr_number}, assuming it's not a release branch")
        return False

    try:
        pr_data = json.loads(stdout)
        branch_name = pr_data.get("headRefName", "").lower()
        # Check if branch name contains common release branch patterns
        release_patterns = ["release", "rel-", "hotfix", "patch", "master"]
        return any(pattern in branch_name for pattern in release_patterns)
    except (json.JSONDecodeError, KeyError):
        print(f"⚠️ Could not parse branch name for PR #{pr_number}, assuming it's not a release branch")
        return False


def get_pr_branch_name(pr_number: int) -> str:
    """Get the branch name for a PR."""
    success, stdout, stderr = run_gh_command(["pr", "view", str(pr_number), "--json", "headRefName"], check=False)
    if not success:
        print(f"⚠️ Could not get branch name for PR #{pr_number}")
        return ""

    try:
        pr_data = json.loads(stdout)
        return pr_data.get("headRefName", "")
    except (json.JSONDecodeError, KeyError):
        print(f"⚠️ Could not parse branch name for PR #{pr_number}")
        return ""


def wait_for_workflows_to_complete(pr_number: int, branch_name: str, max_wait: int = 300, merge_start_time: str = None) -> bool:
    """
    Wait for any remaining workflows to complete after merge, specifically looking for
    workflows running on the PR branch that might still be running.

    Args:
        pr_number: The PR number
        branch_name: The PR branch name to filter workflows by
        max_wait: Maximum seconds to wait (default: 5 minutes)
        merge_start_time: ISO timestamp when merge process started (for filtering)

    Returns:
        True if workflows completed or no workflows found, False if timeout
    """
    import datetime

    if not branch_name:
        print(f"⚠️ No branch name provided, skipping workflow wait")
        return True

    # Parse merge start time or use current time as fallback
    if merge_start_time:
        try:
            merge_time = datetime.datetime.fromisoformat(merge_start_time.replace('Z', '+00:00'))
            print(f"⏳ Waiting for workflows on branch '{branch_name}' created after {merge_start_time} to complete...")
        except (ValueError, TypeError):
            merge_time = datetime.datetime.now(datetime.timezone.utc)
            print(f"⚠️ Invalid merge start time, using current time as reference")
    else:
        merge_time = datetime.datetime.now(datetime.timezone.utc)
        print(f"⏳ Waiting for recent workflows on branch '{branch_name}' to complete...")

    wait_time = 0
    check_interval = 10

    while wait_time < max_wait:
        # Check workflows running on the specific PR branch triggered by issue_comment events
        # This catches workflows like pr-test.yaml triggered by "ok to test" comments
        # Include both queued (waiting for runner) and in_progress (actively running) workflows
        running_workflows = []

        # Check for queued workflows (waiting for runners) on this branch from issue_comment events
        success, stdout, stderr = run_gh_command([
            "run", "list",
            "--branch", branch_name,
            "--event", "issue_comment",
            "--limit", "30",
            "--status", "queued",
            "--json", "status,conclusion,workflowName,workflowDatabaseId,createdAt,event"
        ], check=False)

        if success:
            try:
                queued_workflows = json.loads(stdout)
                running_workflows.extend(queued_workflows)
            except (json.JSONDecodeError, KeyError):
                pass

        # Check for in_progress workflows (actively running) on this branch from issue_comment events
        success, stdout, stderr = run_gh_command([
            "run", "list",
            "--branch", branch_name,
            "--event", "issue_comment",
            "--limit", "30",
            "--status", "in_progress",
            "--json", "status,conclusion,workflowName,workflowDatabaseId,createdAt,event"
        ], check=False)

        if success:
            try:
                in_progress_workflows = json.loads(stdout)
                running_workflows.extend(in_progress_workflows)
            except (json.JSONDecodeError, KeyError):
                pass

        if not running_workflows:
            print(f"⚠️ Could not check workflow status, assuming workflows are complete")
            return True

        try:

            # Filter workflows created after merge process started
            now = datetime.datetime.now(datetime.timezone.utc)
            branch_workflows = []

            for workflow in running_workflows:
                workflow_name = workflow.get("workflowName", "")
                created_at = workflow.get("createdAt", "")

                try:
                    created_time = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))

                    # Only include workflows created after our merge process started
                    if created_time >= merge_time:
                        branch_workflows.append(workflow)
                        status = workflow.get("status", "unknown")
                        event = workflow.get("event", "unknown")
                        time_since_merge = (created_time - merge_time).total_seconds()
                        print(f"  Found workflow on branch '{branch_name}': {workflow_name} [{status}] [{event}] (created {time_since_merge:.0f}s after merge started)")
                    else:
                        # Log workflows that were created before merge (for debugging)
                        time_before_merge = (merge_time - created_time).total_seconds()
                        event = workflow.get("event", "unknown")
                        print(f"  Ignoring pre-merge workflow: {workflow_name} [{event}] (created {time_before_merge:.0f}s before merge)")
                except (ValueError, TypeError):
                    pass

            if not branch_workflows:
                print(f"✅ No running workflows found on branch '{branch_name}'")
                return True

            print(f"⏳ Found {len(branch_workflows)} running workflow(s) on branch '{branch_name}', waiting {check_interval}s...")
            for workflow in branch_workflows:
                workflow_name = workflow.get("workflowName", "unknown")
                workflow_id = workflow.get("workflowDatabaseId", "unknown")
                print(f"  - {workflow_name} (ID: {workflow_id}): {workflow.get('status', 'unknown')}")

        except (json.JSONDecodeError, KeyError):
            print(f"⚠️ Could not parse workflow status, assuming workflows are complete")
            return True

        time.sleep(check_interval)
        wait_time += check_interval

    print(f"⏰ Timeout waiting for workflows to complete after {max_wait}s")
    return False


def delete_branch_after_merge(branch_name: str) -> bool:
    """Delete a branch after merge."""
    if not branch_name:
        return False

    print(f"🗑️ Deleting branch '{branch_name}'...")
    success, stdout, stderr = run_gh_command(["api", "-X", "DELETE", f"/repos/:owner/:repo/git/refs/heads/{branch_name}"], check=False)

    if not success:
        print(f"⚠️ Failed to delete branch '{branch_name}'")
        if stderr:
            print(f"Error: {stderr}")
        return False

    print(f"✅ Successfully deleted branch '{branch_name}'")
    return True


def merge_pr(pr_number: int, workflow_cleanup_wait: int = 300, merge_start_time: str = None) -> bool:
    """Merge a PR using squash merge."""
    print(f"Merging PR #{pr_number} with squash...")

    # Get branch name before merging (needed for cleanup)
    branch_name = get_pr_branch_name(pr_number)

    # Check if this is a release branch to determine if we should delete it later
    should_delete_branch = not is_release_branch(pr_number)

    # Always merge without deleting branch initially to avoid workflow failures
    merge_args = ["pr", "merge", str(pr_number), "--squash", "--admin"]
    print(f"Merging without immediate branch deletion to allow workflows to complete...")

    success, stdout, stderr = run_gh_command(merge_args, check=False)

    if not success:
        print(f"⚠️ Failed to merge PR #{pr_number}")
        if stderr:
            print(f"Error: {stderr}")
        return False

    print(f"✅ Successfully merged PR #{pr_number}")

    # If it's a feature branch, wait for workflows to complete then delete the branch
    if should_delete_branch and branch_name:
        print(f"Feature branch detected, will delete '{branch_name}' after workflows complete...")

        # Wait for any remaining workflows to complete
        if wait_for_workflows_to_complete(pr_number, branch_name, workflow_cleanup_wait, merge_start_time):
            delete_branch_after_merge(branch_name)
        else:
            print(f"⚠️ Workflows did not complete in time, leaving branch '{branch_name}' for manual cleanup")
    else:
        print(f"Release branch detected, keeping branch '{branch_name}'")

    return True


def set_github_output(name: str, value: str):
    """Set GitHub Actions output."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"Output: {name}={value}")


def main():
    """Main function to merge PRs sequentially."""
    import datetime

    # Record when merge process started (for filtering workflows)
    merge_start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Get environment variables
    mergeable_prs_json = get_env_var("MERGEABLE_PRS", "[]")
    default_branch = get_env_var("DEFAULT_BRANCH", "master")
    max_wait_seconds = int(get_env_var("MAX_WAIT_SECONDS", "2700"))  # 45 minutes
    check_interval = int(get_env_var("CHECK_INTERVAL", "30"))  # 30 seconds
    max_startup_wait = int(get_env_var("MAX_STARTUP_WAIT", "300"))  # 5 minutes
    workflow_cleanup_wait = int(get_env_var("WORKFLOW_CLEANUP_WAIT", "300"))  # 5 minutes
    required_check = get_env_var("REQUIRED_CI_CHECK", "run-tests")  # Default to "run-tests"

    print("=== DEBUG: Merge Job Started ===")
    print(f"Merge start time: {merge_start_time}")
    print(f"Mergeable PRs JSON: {mergeable_prs_json}")
    print(f"Default branch: {default_branch}")
    print(f"Max wait time: {max_wait_seconds}s")
    print(f"Check interval: {check_interval}s")
    print(f"Max startup wait: {max_startup_wait}s")
    print(f"Workflow cleanup wait: {workflow_cleanup_wait}s")
    print(f"Required CI check: {required_check}")
    print("================================")
    
    # Parse and sort PRs
    pr_numbers = parse_mergeable_prs(mergeable_prs_json)
    
    if not pr_numbers:
        print("No mergeable PRs to process.")
        # Set empty outputs
        for output_name in ["merged", "failed_update", "failed_ci", "timeout", "failed_merge", "startup_timeout"]:
            set_github_output(output_name, "")
        return 0
    
    print(f"PRs will be merged in chronological order: {pr_numbers}")
    
    # Initialize tracking lists
    merged = []
    failed_update = []
    failed_ci = []
    timeout = []
    failed_merge = []
    startup_timeout = []
    
    # Process each PR
    for pr_number in pr_numbers:
        print(f"\nProcessing PR #{pr_number}...")
        
        # Step 1: Update with default branch
        if not update_pr_branch(pr_number, default_branch):
            failed_update.append(str(pr_number))
            continue
        
        # Step 2: Trigger CI
        if not trigger_ci(pr_number):
            failed_update.append(str(pr_number))  # Treat CI trigger failure as update failure
            continue

        # Step 3: Wait for CI to complete
        print(f"🔄 Starting CI monitoring for PR #{pr_number}...")
        ci_result = wait_for_ci(pr_number, max_wait_seconds, check_interval, max_startup_wait, required_check)

        if ci_result == "failed":
            failed_ci.append(str(pr_number))
            continue
        elif ci_result == "timeout":
            timeout.append(str(pr_number))
            continue
        elif ci_result == "startup_timeout":
            startup_timeout.append(str(pr_number))
            continue
        
        # Step 4: Merge the PR
        if merge_pr(pr_number, workflow_cleanup_wait, merge_start_time):
            merged.append(str(pr_number))
            # Wait for merge to complete before processing next PR
            time.sleep(10)
        else:
            failed_merge.append(str(pr_number))
    
    # Set outputs (comma-separated strings)
    set_github_output("merged", ",".join(merged))
    set_github_output("failed_update", ",".join(failed_update))
    set_github_output("failed_ci", ",".join(failed_ci))
    set_github_output("timeout", ",".join(timeout))
    set_github_output("failed_merge", ",".join(failed_merge))
    set_github_output("startup_timeout", ",".join(startup_timeout))
    
    # Print summary
    print(f"\n=== Merge Summary ===")
    print(f"Total PRs processed: {len(pr_numbers)}")
    print(f"Successfully merged: {len(merged)} - {merged}")
    print(f"Failed to update: {len(failed_update)} - {failed_update}")
    print(f"Failed CI: {len(failed_ci)} - {failed_ci}")
    print(f"CI execution timed out: {len(timeout)} - {timeout}")
    print(f"CI startup timed out: {len(startup_timeout)} - {startup_timeout}")
    print(f"Failed to merge: {len(failed_merge)} - {failed_merge}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
