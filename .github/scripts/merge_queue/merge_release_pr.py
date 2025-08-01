#!/usr/bin/env python3
"""
Merge release PR with proper branch protection checking.

This script merges a release PR using the same branch protection logic
as the regular PR merge process, avoiding code duplication.
"""

import json
import os
import sys

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def main():
    """Main function to merge release PR."""
    # Get environment variables
    release_pr = GitHubUtils.get_env_var("RELEASE_PR")
    repository = GitHubUtils.get_env_var("REPOSITORY")
    default_branch = GitHubUtils.get_env_var("DEFAULT_BRANCH")
    
    print(f"Merging release PR #{release_pr} into {default_branch}...")
    
    # Get PR details including title and source branch
    result = GitHubUtils.get_pr_details(release_pr, "title,headRefName")
    
    if not result.success:
        print(f"❌ Failed to get PR details: {result.stderr}")
        sys.exit(1)
    
    try:
        pr_data = json.loads(result.stdout)
        pr_title = pr_data.get("title", "Unknown Title")
        source_branch = pr_data.get("headRefName", "")
        
        print(f"PR Title: {pr_title}")
        print(f"Source Branch: {source_branch}")
        
        if not source_branch:
            print("❌ Could not determine source branch name")
            sys.exit(1)
            
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse PR data: {e}")
        sys.exit(1)
    
    # Check if source branch is protected using GitHubUtils
    print(f"Checking if source branch '{source_branch}' is protected...")
    is_branch_protected = GitHubUtils.is_branch_protected(repository, source_branch)
    
    # Determine merge flags
    delete_branch_flag = [] if is_branch_protected else ["--delete-branch"]
    
    if delete_branch_flag:
        print(f"✅ Source branch '{source_branch}' is not protected - will delete branch after merge")
    else:
        print(f"✅ Source branch '{source_branch}' is protected - keeping branch after merge")
    
    # Prepare merge command
    merge_message = f"[Merge Queue] {pr_title}"
    print(f"Using merge message: '{merge_message}'")
    
    # Execute merge
    merge_args = ["pr", "merge", release_pr, "--merge", "--admin", "--subject", merge_message] + delete_branch_flag
    result = GitHubUtils._run_gh_command(merge_args, check=False)
    
    if result.success:
        print(f"✅ Successfully merged release PR #{release_pr}")
        return 0
    else:
        print(f"❌ Failed to merge release PR #{release_pr}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
