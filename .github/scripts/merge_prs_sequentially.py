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

import json
import os
import subprocess
import sys
import time
from typing import List, Dict, Tuple


def get_env_var(name: str, default: str = "") -> str:
    """Get environment variable with optional default."""
    return os.environ.get(name, default)


def run_gh_command(args: List[str], check: bool = True) -> Tuple[bool, str, str]:
    """Run a GitHub CLI command and return success, stdout, stderr."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else ""


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
    success, stdout, stderr = run_gh_command(["pr", "comment", str(pr_number), "--body", "ok to test"], check=False)
    
    if not success:
        print(f"⚠️ Failed to trigger CI for PR #{pr_number}")
        if stderr:
            print(f"Error: {stderr}")
        return False
    
    print(f"✅ CI triggered for PR #{pr_number}")
    return True


def get_pr_status_checks(pr_number: int) -> Tuple[int, int]:
    """Get the count of pending and failed status checks for a PR."""
    success, stdout, stderr = run_gh_command(["pr", "view", str(pr_number), "--json", "statusCheckRollup"], check=False)
    
    if not success:
        print(f"⚠️ Failed to get status checks for PR #{pr_number}")
        return 0, 1  # Assume failure if we can't get status
    
    try:
        status_info = json.loads(stdout)
        checks = status_info.get("statusCheckRollup", [])
        
        pending_count = sum(1 for check in checks if check.get("state") in ["PENDING", "IN_PROGRESS"])
        failed_count = sum(1 for check in checks if check.get("state") in ["FAILURE", "ERROR"])
        
        return pending_count, failed_count
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ Error parsing status checks for PR #{pr_number}: {e}")
        return 0, 1  # Assume failure if we can't parse


def wait_for_ci(pr_number: int, max_wait_seconds: int = 2700, check_interval: int = 30) -> str:
    """
    Wait for CI to complete on a PR.
    
    Returns:
        "success" - All checks passed
        "failed" - Some checks failed
        "timeout" - Timed out waiting for checks
    """
    print(f"Waiting for CI to complete for PR #{pr_number}...")
    wait_time = 0
    
    while wait_time < max_wait_seconds:
        pending_checks, failed_checks = get_pr_status_checks(pr_number)
        
        if pending_checks == 0:
            if failed_checks == 0:
                print(f"✅ All CI checks passed for PR #{pr_number}")
                return "success"
            else:
                print(f"❌ CI checks failed for PR #{pr_number}, skipping merge")
                return "failed"
        
        print(f"CI still running for PR #{pr_number}... waiting {check_interval}s ({wait_time}/{max_wait_seconds}s elapsed)")
        time.sleep(check_interval)
        wait_time += check_interval
    
    print(f"⏰ Timeout waiting for CI on PR #{pr_number}, skipping merge")
    return "timeout"


def merge_pr(pr_number: int) -> bool:
    """Merge a PR using squash merge."""
    print(f"Merging PR #{pr_number} with squash...")
    success, stdout, stderr = run_gh_command(["pr", "merge", str(pr_number), "--squash", "--admin", "--delete-branch"], check=False)
    
    if not success:
        print(f"⚠️ Failed to merge PR #{pr_number}")
        if stderr:
            print(f"Error: {stderr}")
        return False
    
    print(f"✅ Successfully merged PR #{pr_number}")
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
    # Get environment variables
    mergeable_prs_json = get_env_var("MERGEABLE_PRS", "[]")
    default_branch = get_env_var("DEFAULT_BRANCH", "main")
    max_wait_seconds = int(get_env_var("MAX_WAIT_SECONDS", "2700"))  # 45 minutes
    check_interval = int(get_env_var("CHECK_INTERVAL", "30"))  # 30 seconds
    
    print("=== DEBUG: Merge Job Started ===")
    print(f"Mergeable PRs JSON: {mergeable_prs_json}")
    print(f"Default branch: {default_branch}")
    print(f"Max wait time: {max_wait_seconds}s")
    print(f"Check interval: {check_interval}s")
    print("================================")
    
    # Parse and sort PRs
    pr_numbers = parse_mergeable_prs(mergeable_prs_json)
    
    if not pr_numbers:
        print("No mergeable PRs to process.")
        # Set empty outputs
        for output_name in ["merged", "failed_update", "failed_ci", "timeout", "failed_merge"]:
            set_github_output(output_name, "")
        return 0
    
    print(f"PRs will be merged in chronological order: {pr_numbers}")
    
    # Initialize tracking lists
    merged = []
    failed_update = []
    failed_ci = []
    timeout = []
    failed_merge = []
    
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
        ci_result = wait_for_ci(pr_number, max_wait_seconds, check_interval)
        
        if ci_result == "failed":
            failed_ci.append(str(pr_number))
            continue
        elif ci_result == "timeout":
            timeout.append(str(pr_number))
            continue
        
        # Step 4: Merge the PR
        if merge_pr(pr_number):
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
    
    # Print summary
    print(f"\n=== Merge Summary ===")
    print(f"Total PRs processed: {len(pr_numbers)}")
    print(f"Successfully merged: {len(merged)} - {merged}")
    print(f"Failed to update: {len(failed_update)} - {failed_update}")
    print(f"Failed CI: {len(failed_ci)} - {failed_ci}")
    print(f"Timed out: {len(timeout)} - {timeout}")
    print(f"Failed to merge: {len(failed_merge)} - {failed_merge}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
