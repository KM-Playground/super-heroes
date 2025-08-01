#!/usr/bin/env python3
"""
Merge PRs sequentially in chronological order.

This script handles the complete merge process:
1. Sort PRs by number (chronological order)
2. Update each PR with the default branch
3. Trigger CI by commenting "Ok to test" and capture comment URL
4. Wait for "CI job started" comment with workflow run ID
5. Wait for the specific workflow run to complete
6. Merge the PR if CI passes
7. Track results and failures
"""

import json
import os
import sys
import time
from typing import List
import datetime

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def parse_iso_datetime(iso_string: str) -> datetime.datetime:
  """
    Parse ISO datetime string, handling both Z and +00:00 timezone formats.

    Args:
        iso_string: ISO datetime string (e.g., "2025-07-16T14:47:52Z" or "2025-07-16T14:47:52+00:00")

    Returns:
        datetime.datetime object with timezone info

    Raises:
        ValueError: If the datetime string cannot be parsed
    """
  if not iso_string:
    raise ValueError("Empty datetime string")

  # Handle Z timezone format by converting to +00:00 for fromisoformat compatibility
  if iso_string.endswith('Z'):
    # Convert Z to +00:00: 2025-07-16T14:47:52Z -> 2025-07-16T14:47:52+00:00
    normalized_string = iso_string.replace('Z', '+00:00')
  else:
    # Assume it already has timezone info
    normalized_string = iso_string

  return datetime.datetime.fromisoformat(normalized_string)


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
  result = GitHubUtils.update_pr_branch(str(pr_number))

  if not result.success:
    print(f"⚠️ Failed to update PR #{pr_number} with {default_branch}")
    if result.error_details:
      print(f"Error: {result.error_details}")
    return False

  print(f"✅ Successfully updated PR #{pr_number}")
  return True


def trigger_ci_and_get_timestamp(pr_number: int) -> str:
  """Trigger CI by commenting 'Ok to test' on the PR and return the comment timestamp."""
  print(f"Triggering CI for PR #{pr_number}...")

  # Post comment and parse stdout to get comment ID
  result = GitHubUtils.trigger_ci_comment(str(pr_number))

  if not result.success:
    print(f"⚠️ Failed to trigger CI for PR #{pr_number}")
    if result.stderr:
      print(f"Error: {result.stderr}")
    return ""

  # Parse comment ID from stdout (usually contains the comment URL)
  # Expected format: https://github.com/owner/repo/issues/123#issuecomment-1234567890
  import re
  comment_id_match = re.search(r'issuecomment-(\d+)', result.stdout)
  if not comment_id_match:
    print(f"⚠️ Could not extract comment ID from output: {result.stdout}")
    return ""

  comment_id = comment_id_match.group(1)
  print(f"✅ CI triggered for PR #{pr_number}, comment ID: {comment_id}")

  # Get the precise timestamp of the comment using GitHub API
  result = GitHubUtils.get_comment_timestamp(comment_id)

  if not result.success:
    print(f"⚠️ Failed to get comment timestamp for comment {comment_id}")
    if result.stderr:
      print(f"Error: {result.stderr}")
    return ""

  try:
    comment_details = json.loads(result.stdout)
    created_at = comment_details.get("created_at", "")

    if not created_at:
      print(f"⚠️ Could not get created_at timestamp for comment {comment_id}")
      return ""

    print(f"✅ Comment created at: {created_at}")
    return created_at

  except (json.JSONDecodeError, KeyError):
    print(f"⚠️ Could not parse comment details for comment {comment_id}")
    return ""


def wait_for_ci_job_started_comment(pr_number: int, trigger_time: str,
    max_wait: int) -> str:
  """
    Wait for the 'CI job started' comment and extract the run ID.

    Args:
        pr_number: The PR number
        trigger_time: ISO timestamp when we posted the "Ok to test" comment
        max_wait: Maximum seconds to wait for the comment

    Returns:
        Run ID if found, empty string if not found or timeout
    """
  print(f"⏳ Waiting for 'CI job started' comment on PR #{pr_number}...")

  # Parse trigger time
  try:
    trigger_datetime = parse_iso_datetime(trigger_time)
  except (ValueError, TypeError) as e:
    print(f"⚠️ Invalid trigger time format '{trigger_time}': {e}")
    return ""

  wait_time = 0
  check_interval = 5

  while wait_time < max_wait:
    # Get recent comments on the PR
    result = GitHubUtils.get_pr_comments(str(pr_number))

    if not result.success:
      print(f"⚠️ Failed to get comments for PR #{pr_number}")
      time.sleep(check_interval)
      wait_time += check_interval
      continue

    try:
      pr_data = json.loads(result.stdout)
      comments = pr_data.get("comments", [])

      # Look for comments posted after our trigger time
      for comment in comments:
        comment_body = comment.get("body", "")
        created_at = comment.get("createdAt", "")

        try:
          # Parse comment timestamp
          comment_time = parse_iso_datetime(created_at)
        except (ValueError, TypeError):
          # Skip comments with invalid timestamps
          continue

        # Skip comments created before our trigger
        if comment_time <= trigger_datetime:
          continue

        # Look for "CI job started" pattern with run ID
        # Sample comment looks like this
        # ✅ CI job started: [View Workflow Run](https://github.com/owner/repo/actions/runs/12345)
        if "CI job started" in comment_body and "actions/runs/" in comment_body:
          # Extract run ID from URL like: https://github.com/owner/repo/actions/runs/12345
          import re
          run_id_match = re.search(r'actions/runs/(\d+)', comment_body)
          if run_id_match:
            run_id = run_id_match.group(1)
            print(f"✅ Found CI job started comment with run ID: {run_id}")
            return run_id

    except (json.JSONDecodeError, KeyError) as e:
      print(f"⚠️ Error parsing comments for PR #{pr_number}: {e}")

    print(
      f"⏳ No CI job started comment yet, waiting {check_interval}s... ({wait_time}/{max_wait}s elapsed)")
    time.sleep(check_interval)
    wait_time += check_interval

  print(f"⏰ Timeout waiting for CI job started comment on PR #{pr_number}")
  return ""


def wait_for_workflow_run_completion(run_id: str, max_wait: int,
    check_interval: int) -> str:
  """
    Wait for a specific workflow run to complete.

    Args:
        run_id: The workflow run ID to monitor
        max_wait: Maximum seconds to wait for completion
        check_interval: Seconds between status checks

    Returns:
        "success" - Workflow completed successfully
        "failed" - Workflow failed
        "timeout" - Timed out waiting for completion
    """
  print(f"⏳ Monitoring workflow run {run_id} for completion...")

  wait_time = 0

  while wait_time < max_wait:
    # Get workflow run status
    result = GitHubUtils.get_workflow_run_status(run_id)

    if not result.success:
      print(f"⚠️ Failed to get status for workflow run {run_id}")
      time.sleep(check_interval)
      wait_time += check_interval
      continue

    try:
      run_data = json.loads(result.stdout)
      status = run_data.get("status", "")
      conclusion = run_data.get("conclusion", "")
      workflow_name = run_data.get("workflowName", "unknown")

      print(
        f"📊 Workflow '{workflow_name}' (ID: {run_id}) - Status: {status}, Conclusion: {conclusion}")

      # Check if workflow is complete
      if status == "completed":
        if conclusion == "success":
          print(f"✅ Workflow run {run_id} completed successfully")
          return "success"
        else:
          print(f"❌ Workflow run {run_id} failed with conclusion: {conclusion}")
          return "failed"
      elif status in ["queued", "in_progress"]:
        print(
          f"⏳ Workflow run {run_id} still running, waiting {check_interval}s... ({wait_time}/{max_wait}s elapsed)")
      else:
        print(f"⚠️ Unexpected workflow status: {status}")

    except (json.JSONDecodeError, KeyError) as e:
      print(f"⚠️ Error parsing workflow run data: {e}")

    time.sleep(check_interval)
    wait_time += check_interval

  print(f"⏰ Timeout waiting for workflow run {run_id} to complete")
  return "timeout"





def merge_pr(pr_number: int, repository: str) -> bool:
  """Merge a PR using squash merge and delete branch if it's a feature branch."""
  print(f"Merging PR #{pr_number} with squash...")

  # First, check if PR is still mergeable
  result = GitHubUtils.get_pr_details(str(pr_number), "mergeable,state,author")

  if result.success:
    try:
      pr_data = json.loads(result.stdout)
      mergeable = pr_data.get("mergeable", "")
      state = pr_data.get("state", "")
      author = pr_data.get("author", {}).get("login", "")

      if state != "OPEN":
        print(f"⚠️ PR #{pr_number} is not open (state: {state})")
        return False

      if mergeable == "CONFLICTING":
        print(f"⚠️ PR #{pr_number} has merge conflicts (mergeable: {mergeable})")

        # Add immediate comment about merge conflicts
        if author:
          conflict_message = f"@{author} ⚠️ **Merge Conflicts Detected**\n\nThis PR has merge conflicts that prevent it from being merged automatically. The conflicts likely occurred after the latest changes were merged to the main branch.\n\n**Next Steps:**\n1. Pull the latest changes from the main branch\n2. Resolve the merge conflicts in your branch\n3. Push the resolved changes\n4. The PR will be ready for the next merge cycle\n\n*This comment was automatically generated by the merge queue workflow.*"

          comment_result = GitHubUtils.comment_on_pr(str(pr_number), conflict_message)

          if not comment_result.success:
            print(f"⚠️ Failed to add merge conflict comment to PR #{pr_number}: {comment_result.error_details}")

        return False

    except (json.JSONDecodeError, KeyError) as e:
      print(f"⚠️ Could not parse PR status for #{pr_number}: {e}")
      # Continue with merge attempt anyway

  # Get PR branch name for merge message and protection check
  branch_result = GitHubUtils.get_pr_branch_name(str(pr_number))
  branch_name = "unknown-branch"
  should_delete_branch = False  # Default to safe option

  if branch_result.success:
    try:
      branch_data = json.loads(branch_result.stdout)
      branch_name = branch_data.get("headRefName", "unknown-branch")
      print(f"✅ Retrieved branch name: {branch_name}")

      # Check if this branch is protected to determine if we should delete it
      if branch_name != "unknown-branch":
        print(f"Checking if branch '{branch_name}' is protected...")
        is_branch_protected = GitHubUtils.is_branch_protected(repository, branch_name)
        should_delete_branch = not is_branch_protected

        if should_delete_branch:
          print(f"Will delete branch after merge (non-protected branch)")
        else:
          print(f"Will keep branch after merge (protected branch)")
      else:
        print(f"Will keep branch after merge (unknown branch name - safe default)")

    except (json.JSONDecodeError, KeyError) as e:
      print(f"⚠️ Could not parse branch name for PR #{pr_number}: {e}")
      print(f"Will keep branch after merge (safe default)")
      # Continue with default branch name and safe deletion setting
  else:
    print(f"⚠️ Could not get branch name for PR #{pr_number}: {branch_result.stderr}")
    print(f"Will keep branch after merge (safe default)")
    # Continue with default branch name and safe deletion setting

  # Generate merge message in the required format
  merge_message = f"[Merge Queue]Merge Pull Request #{pr_number} from {branch_name}"
  print(f"Using merge message: '{merge_message}'")

  result = GitHubUtils.merge_pr(
    str(pr_number),
    squash=True,
    delete_branch=should_delete_branch,
    merge_message=merge_message,
    admin=True
  )

  if not result.success:
    print(f"⚠️ Failed to merge PR #{pr_number}")
    if result.stderr:
      print(f"Error: {result.stderr}")
    if result.stdout:
      print(f"Output: {result.stdout}")
    return False

  # Additional check: verify the merge was actually successful
  # Sometimes gh pr merge returns success but the PR is still open due to conflicts
  result = GitHubUtils.get_pr_details(str(pr_number), "state")

  if result.success:
    try:
      pr_data = json.loads(result.stdout)
      final_state = pr_data.get("state", "")
      if final_state == "MERGED":
        print(f"✅ Successfully merged PR #{pr_number}")
        return True
      else:
        print(f"⚠️ PR #{pr_number} merge command succeeded but PR is still {final_state}")
        return False
    except (json.JSONDecodeError, KeyError) as e:
      print(f"⚠️ Could not verify merge status for PR #{pr_number}: {e}")
      # Assume success if we can't verify
      print(f"✅ Merge command succeeded for PR #{pr_number} (could not verify final state)")
      return True
  else:
    # Assume success if we can't check the final state
    print(f"✅ Merge command succeeded for PR #{pr_number} (could not check final state)")
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
  # Get environment variables - no defaults, must be set
  mergeable_prs_json = GitHubUtils.get_env_var("MERGEABLE_PRS")
  default_branch = GitHubUtils.get_env_var("DEFAULT_BRANCH")
  repository = GitHubUtils.get_env_var("REPOSITORY")
  max_wait_seconds = int(GitHubUtils.get_env_var("MAX_WAIT_SECONDS"))
  check_interval = int(GitHubUtils.get_env_var("CHECK_INTERVAL"))
  max_startup_wait = int(GitHubUtils.get_env_var("MAX_STARTUP_WAIT"))

  print("=== DEBUG: Merge Job Started ===")
  print(f"Mergeable PRs JSON: {mergeable_prs_json}")
  print(f"Default branch: {default_branch}")
  print(f"Repository: {repository}")
  print(f"Max wait time: {max_wait_seconds}s")
  print(f"Check interval: {check_interval}s")
  print(f"Max startup wait: {max_startup_wait}s")
  print("Merge messages will be generated dynamically for each PR")
  print("================================")

  # Parse and sort PRs
  pr_numbers = parse_mergeable_prs(mergeable_prs_json)

  if not pr_numbers:
    print("No mergeable PRs to process.")
    # Set empty outputs
    for output_name in ["merged", "failed_update", "failed_ci", "timeout",
                        "failed_merge", "startup_timeout"]:
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

    # Step 2: Trigger CI and get timestamp
    trigger_timestamp = trigger_ci_and_get_timestamp(pr_number)
    if not trigger_timestamp:
      failed_update.append(
        str(pr_number))  # Treat CI trigger failure as update failure
      continue

    # Step 3: Wait for CI job started comment with run ID
    print(f"🔄 Waiting for CI job started comment on PR #{pr_number}...")
    run_id = wait_for_ci_job_started_comment(pr_number, trigger_timestamp,
                                             max_startup_wait)
    if not run_id:
      startup_timeout.append(str(pr_number))
      continue

    # Step 4: Wait for the specific workflow run to complete
    print(f"🔄 Monitoring workflow run {run_id} for PR #{pr_number}...")
    ci_result = wait_for_workflow_run_completion(run_id, max_wait_seconds,
                                                 check_interval)

    if ci_result == "failed":
      failed_ci.append(str(pr_number))
      continue
    elif ci_result == "timeout":
      timeout.append(str(pr_number))
      continue
    elif ci_result == "startup_timeout":
      startup_timeout.append(str(pr_number))
      continue

    # Step 5: Merge the PR
    if merge_pr(pr_number, repository):
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
