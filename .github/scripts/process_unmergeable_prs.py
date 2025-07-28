#!/usr/bin/env python3
"""
Process unmergeable PRs and generate appropriate comments.

This script combines initially unmergeable PRs (from validation) and PRs that failed
during the merge process, then generates appropriate comments for each PR author.
"""

import json
import sys
from typing import List

from gh_utils import get_env_var, get_pr_author, comment_on_pr


def parse_json_array(json_str: str) -> List[str]:
    """Parse JSON array string, return empty list if invalid."""
    if not json_str or json_str.strip() == "":
        return []
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse JSON array: {json_str}")
        return []


def parse_comma_separated(csv_str: str) -> List[str]:
    """Parse comma-separated string, return empty list if invalid."""
    if not csv_str or csv_str.strip() == "":
        return []
    return [pr.strip() for pr in csv_str.split(",") if pr.strip()]





def generate_validation_failure_message(author: str, required_approvals: str, default_branch: str) -> str:
    """Generate message for PRs that failed initial validation."""
    return f"""❌ @{author}, this PR could not be merged due to one or more of the following:

- Less than {required_approvals} approvals
- Failing or missing status checks
- Not up-to-date with `{default_branch}`
- Not targeting `{default_branch}`

Please address these issues to include it in the next merge cycle."""


def generate_merge_failure_message(author: str) -> str:
    """Generate message for PRs that failed during merge process."""
    return f"""❌ @{author}, this PR passed initial validation but failed during the merge process. This could be due to:

- Merge conflicts that developed after validation
- GitHub API errors during merge
- Branch protection rule changes

Please check the PR status and try again in the next merge cycle."""


def main():
    """Main function to process unmergeable PRs."""
    # Get environment variables - no defaults, must be set
    initial_unmergeable_json = get_env_var("INITIAL_UNMERGEABLE_PRS")
    failed_merge_csv = get_env_var("FAILED_MERGE_PRS")
    required_approvals = get_env_var("REQUIRED_APPROVALS")
    default_branch = get_env_var("DEFAULT_BRANCH")
    
    print("=== Processing Unmergeable PRs ===")
    print(f"Initial unmergeable PRs: {initial_unmergeable_json}")
    print(f"Failed merge PRs: {failed_merge_csv}")
    print(f"Required approvals: {required_approvals}")
    print(f"Default branch: {default_branch}")
    
    # Parse input data
    initial_unmergeable = parse_json_array(initial_unmergeable_json)
    failed_merge = parse_comma_separated(failed_merge_csv)
    
    # Create sets for easy lookup
    initial_set = set(initial_unmergeable)
    failed_merge_set = set(failed_merge)
    
    # Combine all unmergeable PRs
    all_unmergeable = list(set(initial_unmergeable + failed_merge))
    
    print(f"Combined unmergeable PRs: {all_unmergeable}")
    
    if not all_unmergeable:
        print("No unmergeable PRs to process.")
        return 0
    
    success_count = 0
    total_count = len(all_unmergeable)
    
    # Process each PR
    for pr_number in all_unmergeable:
        print(f"\nProcessing PR #{pr_number}...")
        
        # Get PR author
        author = get_pr_author(pr_number)
        
        # Determine failure type and generate appropriate message
        if pr_number in initial_set:
            print(f"  Type: Validation failure")
            message = generate_validation_failure_message(author, required_approvals, default_branch)
        elif pr_number in failed_merge_set:
            print(f"  Type: Merge failure")
            message = generate_merge_failure_message(author)
        else:
            print(f"  Warning: PR #{pr_number} not found in either failure category")
            continue
        
        # Comment on the PR
        if comment_on_pr(pr_number, message):
            success_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Total PRs processed: {total_count}")
    print(f"Successful comments: {success_count}")
    print(f"Failed comments: {total_count - success_count}")
    
    # Return non-zero exit code if any comments failed
    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
