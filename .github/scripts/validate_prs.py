#!/usr/bin/env python3
"""
Validate PRs for merge eligibility.

This script validates PRs against the following criteria:
1. Targets the correct base branch (default branch)
2. Has no merge conflicts
3. Has sufficient approvals
4. Has passing status checks
5. Determines required approvals from branch protection or manual input
"""

import os
import json
import sys
from typing import List, Dict, Optional, Tuple

from gh_utils import get_env_var, run_gh_command


def parse_pr_numbers(pr_numbers_str: str) -> List[str]:
    """Parse comma-separated PR numbers."""
    if not pr_numbers_str or pr_numbers_str.strip() == "":
        return []
    return [pr.strip() for pr in pr_numbers_str.split(",") if pr.strip()]


def get_required_approvals(manual_approvals: str, repository: str, default_branch: str) -> int:
    """Determine required approvals from manual input or branch protection."""
    if manual_approvals and manual_approvals.strip():
        try:
            approvals = int(manual_approvals.strip())
            print(f"Using manually specified required approvals: {approvals}")
            return approvals
        except ValueError:
            print(f"Warning: Invalid manual approvals value '{manual_approvals}', falling back to branch protection")
    
    print(f"Attempting to get branch protection rules for {default_branch}...")
    
    # Get branch protection rules
    success, stdout, stderr = run_gh_command([
        "api", f"repos/{repository}/branches/{default_branch}/protection"
    ], check=False)
    
    if not success:
        print("⚠️ Could not access branch protection rules (requires admin permissions)")
        print("⚠️ Defaulting to 1 required approval. Use 'required_approvals' input to override.")
        return 1
    
    try:
        protection_data = json.loads(stdout) if stdout else {}
        required_approvals = protection_data.get("required_pull_request_reviews", {}).get("required_approving_review_count", 0)
        
        if required_approvals == 0 and not protection_data:
            print("⚠️ No branch protection rules found, defaulting to 1 required approval")
            return 1
        
        print(f"Retrieved from branch protection: {required_approvals} required approvals")
        return required_approvals
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Error parsing branch protection data: {e}")
        print("⚠️ Defaulting to 1 required approval")
        return 1


def get_pr_info(pr_number: str) -> Optional[Dict]:
    """Get PR information using GitHub CLI."""
    success, stdout, stderr = run_gh_command([
        "pr", "view", pr_number,
        "--json", "baseRefName,mergeable,headRefName,reviews,statusCheckRollup,state"
    ], check=False)
    
    if not success:
        print(f"❌ Failed to get info for PR #{pr_number}: {stderr}")
        return None
    
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse PR #{pr_number} info: {e}")
        return None


def count_approvals(reviews: List[Dict]) -> int:
    """Count approved reviews."""
    return sum(1 for review in reviews if review.get("state") == "APPROVED")


def get_failing_checks(status_checks: List[Dict]) -> List[str]:
    """Get list of failing or pending status checks."""
    failing = []
    for check in status_checks:
        state = check.get("state", "")
        if state not in ["SUCCESS"]:
            failing.append(f"{check.get('context', 'unknown')}:{state}")
    return failing


def validate_pr(pr_number: str, required_approvals: int, default_branch: str, pr_type: str = "regular") -> Tuple[bool, List[str]]:
    """
    Validate a single PR.

    Args:
        pr_number: The PR number to validate
        required_approvals: Number of required approvals
        default_branch: The default branch (integration branch) that PRs should target
        pr_type: Type of PR ("regular" or "release") for better error messages

    Returns:
        (is_mergeable, reasons_for_failure)
    """
    print(f"Checking {pr_type} PR #{pr_number} (should target '{default_branch}')...")

    # Get PR information
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        return False, ["Failed to retrieve PR information"]
    
    # Extract data
    base_branch = pr_info.get("baseRefName", "")
    mergeable_state = pr_info.get("mergeable", "")
    pr_state = pr_info.get("state", "")
    reviews = pr_info.get("reviews", [])
    status_checks = pr_info.get("statusCheckRollup", [])

    approval_count = count_approvals(reviews)
    failing_checks = get_failing_checks(status_checks)

    # Debug output
    print(f"  Debug - PR #{pr_number} variables:")
    print(f"    PR state: {pr_state}")
    print(f"    Base branch: {base_branch}")
    print(f"    Mergeable state: {mergeable_state}")
    print(f"    Approvals count: {approval_count}")
    print(f"    Required approvals: {required_approvals}")
    print(f"    Failing checks: {failing_checks}")

    # Validation checks
    failure_reasons = []

    # Check if PR is open (most important check - skip already processed PRs)
    if pr_state != "OPEN":
        reason = f"PR is not open (state: {pr_state})"
        print(f"⚠️ PR #{pr_number} {reason} - skipping already processed PR")
        failure_reasons.append(reason)
        return False, failure_reasons
    
    # Check base branch (target validation) - all PRs should target the default branch
    if base_branch != default_branch:
        reason = f"Does not target '{default_branch}' (targets '{base_branch}') - all PRs must target the default branch '{default_branch}'"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)
    
    # Check merge conflicts
    if mergeable_state == "CONFLICTING":
        reason = f"Has merge conflicts (state={mergeable_state})"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)
    elif mergeable_state == "UNKNOWN":
        print(f"⚠️ PR #{pr_number} mergeable state is unknown - will proceed and let GitHub decide")
    
    # Check approvals
    if approval_count < required_approvals:
        reason = f"Has {approval_count} approvals, but {required_approvals} are required"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)
    
    # Check status checks
    if failing_checks:
        reason = f"Has failing/missing checks: {', '.join(failing_checks)}"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)
    
    if not failure_reasons:
        print(f"✅ PR #{pr_number} is mergeable")
        return True, []
    
    return False, failure_reasons


def set_github_output(name: str, value: str):
    """Set GitHub Actions output."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"Output: {name}={value}")


def main():
    """Main function to validate PRs."""
    # Get environment variables - no defaults, must be set
    pr_numbers_str = get_env_var("PR_NUMBERS")
    manual_approvals = get_env_var("REQUIRED_APPROVALS")
    repository = get_env_var("REPOSITORY")
    default_branch = get_env_var("DEFAULT_BRANCH")
    release_pr = get_env_var("RELEASE_PR")

    print("=== DEBUG: All Variables ===")
    print(f"Repository: {repository}")
    print(f"Default branch (target for all PRs): {default_branch}")
    print(f"PR numbers input: {pr_numbers_str}")
    print(f"Release PR: {release_pr}")
    print(f"Required approvals input: {manual_approvals}")
    
    # Parse PR numbers
    pr_numbers = parse_pr_numbers(pr_numbers_str)
    print(f"PR_LIST array: {pr_numbers}")
    print(f"Number of PRs to validate: {len(pr_numbers)}")
    print("============================")
    
    if not pr_numbers:
        print("No PRs to validate.")
        # Set empty outputs
        set_github_output("mergeable", "[]")
        set_github_output("unmergeable", "[]")
        set_github_output("required_approvals", "1")
        set_github_output("has_mergeable", "false")
        set_github_output("has_unmergeable", "false")
        return 0
    
    # Determine required approvals
    required_approvals = get_required_approvals(manual_approvals, repository, default_branch)
    print(f"REQUIRED_APPROVALS (calculated): {required_approvals}")
    
    # Validate each PR
    mergeable_prs = []
    unmergeable_prs = []

    # Validate regular PRs
    for pr_number in pr_numbers:
        is_mergeable, failure_reasons = validate_pr(pr_number, required_approvals, default_branch, "regular")

        if is_mergeable:
            mergeable_prs.append(pr_number)
        else:
            unmergeable_prs.append(pr_number)

    # Validate release PR if provided
    if release_pr and release_pr.strip():
        print(f"\n=== Validating Release PR ===")
        is_mergeable, failure_reasons = validate_pr(release_pr.strip(), required_approvals, default_branch, "release")

        if not is_mergeable:
            print(f"❌ Release PR #{release_pr} validation failed:")
            for reason in failure_reasons:
                print(f"  - {reason}")
            # Note: We don't add release PR to unmergeable_prs as it's handled separately in the workflow
            print(f"⚠️ Release PR validation failed - the release merge step may fail")
        else:
            print(f"✅ Release PR #{release_pr} validation passed")
    
    # Convert to JSON arrays
    mergeable_json = json.dumps(mergeable_prs)
    unmergeable_json = json.dumps(unmergeable_prs)
    
    # Set outputs
    set_github_output("mergeable", mergeable_json)
    set_github_output("unmergeable", unmergeable_json)
    set_github_output("required_approvals", str(required_approvals))
    set_github_output("has_mergeable", "true" if mergeable_prs else "false")
    set_github_output("has_unmergeable", "true" if unmergeable_prs else "false")
    
    # Debug output
    print("\n=== DEBUG: Validate PRs Job Output ===")
    print(f"Mergeable PRs:      {mergeable_json}")
    print(f"Unmergeable PRs:    {unmergeable_json}")
    print(f"Required approvals: {required_approvals}")
    print(f"Has mergeable PRs:  {'true' if mergeable_prs else 'false'}")
    print(f"Has unmergeable PRs: {'true' if unmergeable_prs else 'false'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
