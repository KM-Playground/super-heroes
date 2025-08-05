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

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


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
    result = GitHubUtils.get_branch_protection(repository, default_branch)

    if not result.success:
        print("⚠️ Could not access branch protection rules (requires admin permissions)")
        print("⚠️ Defaulting to 1 required approval. Use 'required_approvals' input to override.")
        return 1

    try:
        protection_data = json.loads(result.stdout) if result.stdout else {}
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
    result = GitHubUtils.get_pr_details(pr_number,
        "baseRefName,mergeable,headRefName,reviews,statusCheckRollup,state,author")

    if not result.success:
        print(f"❌ Failed to get info for PR #{pr_number}: {result.stderr}")
        return None

    try:
        return json.loads(result.stdout)
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


def notify_pr_owner_about_base_branch(pr_number: str, author: str, current_base: str, expected_base: str) -> None:
    """Notify PR owner about incorrect base branch."""
    print(f"📢 Notifying @{author} about base branch issue on PR #{pr_number}")

    notification_message = f"""⚠️ **Base Branch Issue - Action Required**

@{author}, your PR #{pr_number} is targeting the `{current_base}` branch, but the merge queue requires all PRs to target the default branch `{expected_base}`.

**Required Action:**
1. Change the base branch of this PR from `{current_base}` to `{expected_base}`
2. Resolve any merge conflicts that may arise
3. Ensure all status checks pass

**How to Change Base Branch:**
- Go to your PR page
- Click "Edit" next to the PR title
- Change the base branch to `{expected_base}`
- Update your branch if needed: `git rebase origin/{expected_base}`

**Why This Matters:**
The merge queue is designed to merge PRs sequentially into the default branch (`{expected_base}`) to maintain a clean, linear history.

*This is an automated notification from the merge queue validation process.*"""

    result = GitHubUtils.comment_on_pr(pr_number, notification_message)
    if result.success:
        print(f"✅ Successfully notified @{author} about base branch issue on PR #{pr_number}")
    else:
        print(f"⚠️ Failed to notify @{author} about base branch issue on PR #{pr_number}: {result.error_details}")


def notify_pr_owner_about_conflicts(pr_number: str, author: str, base_branch: str) -> None:
    """Notify PR owner about merge conflicts."""
    print(f"📢 Notifying @{author} about merge conflicts on PR #{pr_number}")

    notification_message = f"""⚠️ **Merge Conflicts Detected - Action Required**

@{author}, your PR #{pr_number} has merge conflicts with the `{base_branch}` branch and cannot be merged automatically.

**Required Action:**
1. Update your branch with the latest changes from `{base_branch}`
2. Resolve all merge conflicts
3. Push the resolved changes to your branch
4. Ensure all status checks pass

**Why This Matters:**
The merge queue requires all PRs to be conflict-free to ensure smooth, automated merging and maintain repository stability.

*This is an automated notification from the merge queue validation process.*"""

    result = GitHubUtils.comment_on_pr(pr_number, notification_message)
    if result.success:
        print(f"✅ Successfully notified @{author} about merge conflicts on PR #{pr_number}")
    else:
        print(f"⚠️ Failed to notify @{author} about merge conflicts on PR #{pr_number}: {result.error_details}")


def notify_pr_owner_about_insufficient_approvals(pr_number: str, author: str, current_approvals: int, required_approvals: int) -> None:
    """Notify PR owner about insufficient approvals."""
    print(f"📢 Notifying @{author} about insufficient approvals on PR #{pr_number}")

    notification_message = f"""⚠️ **Insufficient Approvals - Action Required**

@{author}, your PR #{pr_number} currently has {current_approvals} approval(s), but {required_approvals} approval(s) are required for merging.

**Required Action:**
1. Request reviews from team members or maintainers
2. Address any feedback or requested changes
3. Ensure your PR meets all review criteria
4. Wait for the required number of approvals

**Why This Matters:**
The merge queue enforces approval requirements to ensure code quality and maintain proper review processes before merging.

*This is an automated notification from the merge queue validation process.*"""

    result = GitHubUtils.comment_on_pr(pr_number, notification_message)
    if result.success:
        print(f"✅ Successfully notified @{author} about insufficient approvals on PR #{pr_number}")
    else:
        print(f"⚠️ Failed to notify @{author} about insufficient approvals on PR #{pr_number}: {result.error_details}")


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
    author = pr_info.get("author", {}).get("login", "")

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

        # Notify PR owner about the base branch issue
        if author:
            notify_pr_owner_about_base_branch(pr_number, author, base_branch, default_branch)
    
    # Check merge conflicts
    if mergeable_state == "CONFLICTING":
        reason = f"Has merge conflicts (state={mergeable_state})"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)

        # Notify PR owner about merge conflicts
        if author:
            notify_pr_owner_about_conflicts(pr_number, author, default_branch)
    elif mergeable_state == "UNKNOWN":
        print(f"⚠️ PR #{pr_number} mergeable state is unknown - will proceed and let GitHub decide")
    
    # Check approvals
    if approval_count < required_approvals:
        reason = f"Has {approval_count} approvals, but {required_approvals} are required"
        print(f"❌ PR #{pr_number} {reason}")
        failure_reasons.append(reason)

        # Notify PR owner about insufficient approvals
        if author:
            notify_pr_owner_about_insufficient_approvals(pr_number, author, approval_count, required_approvals)
    
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
    pr_numbers_str = GitHubUtils.get_env_var("PR_NUMBERS")
    manual_approvals = GitHubUtils.get_env_var("REQUIRED_APPROVALS")
    repository = GitHubUtils.get_env_var("REPOSITORY")
    default_branch = GitHubUtils.get_env_var("DEFAULT_BRANCH")
    release_pr = GitHubUtils.get_env_var("RELEASE_PR")

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
