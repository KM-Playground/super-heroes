#!/usr/bin/env python3
"""
Initialize Merge Queue with Duplicate Prevention and Tracking Issue Management.

This script handles the complete initialization of the merge queue workflow:
1. Checks for existing tracking issues (duplicate prevention)
2. Extracts PR information from issue body
3. Creates a new tracking issue if none exists
4. Exports all information for later workflow steps
"""

import json
import sys
import os
from dataclasses import dataclass
from typing import Optional

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


@dataclass
class PRExtractionResult:
    """Result of extracting PR information from issue body."""
    pr_numbers: str
    release_pr: Optional[str] = None
    required_approvals: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            'pr_numbers': self.pr_numbers,
            'release_pr': self.release_pr,
            'required_approvals': self.required_approvals
        }


# === Tracking Issue Management Functions ===

def get_tracking_issue_title(original_issue_number: int) -> str:
    """Generate the title for a tracking issue."""
    return f"[MERGE QUEUE TRACKING] Issue #{original_issue_number} - Auto Merge In Progress"


def get_tracking_issue_body(original_issue_number: int, pr_numbers: str, release_pr: Optional[str] = None) -> str:
    """Generate the body for a tracking issue."""
    release_info = ""
    if release_pr and release_pr.strip():
        release_info = f"\n- **Release PR**: #{release_pr.strip()}"

    return f"""🚀 **Merge Queue Tracking Issue**

This issue tracks an active merge queue process to prevent duplicate runs.

**Original Issue**: #{original_issue_number}
**PR Numbers**: {pr_numbers}{release_info}
**Status**: 🔄 In Progress

---

🔒 **Distributed Lock**: This issue uses the `distributed-lock` label to prevent concurrent merge queue runs for the same original issue.

⚠️ **Do not manually close this issue** - it will be closed automatically when the merge queue process completes.

**Monitor Progress**: Check the [original issue](../../issues/{original_issue_number}) for updates.
"""





def create_tracking_issue(original_issue_number: int, pr_numbers: str, release_pr: Optional[str] = None) -> Optional[int]:
    """
    Create a new tracking issue.

    Returns:
        The tracking issue number if created successfully, None otherwise
    """
    print(f"Creating tracking issue for original issue #{original_issue_number}...")

    title = get_tracking_issue_title(original_issue_number)
    body = get_tracking_issue_body(original_issue_number, pr_numbers, release_pr)

    result = GitHubUtils.create_issue(title, body, ["distributed-lock", "automation"])

    if result.success:
        # Extract issue number from the URL in the response
        # Format: https://github.com/owner/repo/issues/123
        try:
            url = result.stdout.strip()

            if "/issues/" in url:
                issue_number = int(url.split("/issues/")[-1])
                print(f"✅ Created tracking issue: #{issue_number}")
                return issue_number
            else:
                print(f"⚠️ Created tracking issue but couldn't parse URL: '{url}'")
                return None
        except (ValueError, IndexError) as e:
            print(f"⚠️ Created tracking issue but failed to parse URL: {e}")
            return None
    else:
        print(f"❌ Failed to create tracking issue: {result.error_details}")
        return None





def initialize_tracking_issue(original_issue_number: int, pr_numbers: str, release_pr: Optional[str] = None) -> Optional[int]:
    """
    Initialize tracking issue for a new merge queue run.

    Returns:
        The tracking issue number if created successfully, None otherwise
    """
    print("=== Tracking Issue Initialization ===")
    print(f"Original Issue: #{original_issue_number}")
    print(f"PR Numbers: {pr_numbers}")
    print(f"Release PR: {release_pr if release_pr else '(none)'}")
    print("====================================")

    return create_tracking_issue(original_issue_number, pr_numbers, release_pr)



# === PR Information Extraction Functions ===


def extract_pr_info_from_issue_body(issue_body: str) -> PRExtractionResult:
    """
    Extract PR numbers, release PR, and required approvals from issue body.

    Supports both formats:
    1. GitHub issue template format with markdown headers (### PR Numbers)
    2. Legacy format with colon-separated lines (PR Numbers: 123)

    Args:
        issue_body: The issue body content

    Returns:
        PRExtractionResult with extracted information
    """
    pr_numbers = "TBD"
    release_pr = None
    required_approvals = None

    if not issue_body:
        return PRExtractionResult(pr_numbers, release_pr, required_approvals)

    lines = issue_body.strip().split('\n')
    current_section = None

    for i, line in enumerate(lines):
        line = line.strip()

        # Check for GitHub issue template markdown headers
        if line.startswith('### '):
            header = line[4:].strip().lower()
            if 'pr numbers' in header:
                current_section = 'pr_numbers'
            elif 'release pr' in header:
                current_section = 'release_pr'
            elif 'required approvals override' in header:
                current_section = 'required_approvals'
            else:
                current_section = None
            continue

        # Legacy format: Look for colon-separated patterns
        if ':' in line:
            if line.lower().startswith('pr numbers:'):
                pr_part = line.split(':', 1)[1].strip()
                # Clean up the PR numbers (remove spaces, handle various formats)
                if pr_part and pr_part.lower() not in ['none', '_no response_', 'tbd']:
                    pr_numbers = ','.join([pr.strip() for pr in pr_part.split(',') if pr.strip()])
                continue

            elif line.lower().startswith('release pr:'):
                release_part = line.split(':', 1)[1].strip()
                if release_part and release_part.lower() not in ['none', '_no response_']:
                    release_pr = release_part
                continue

            elif line.lower().startswith('required approvals override:'):
                approvals_part = line.split(':', 1)[1].strip()
                if approvals_part and approvals_part.lower() not in ['none', '_no response_']:
                    required_approvals = approvals_part
                continue

        # Process content under current section (for GitHub template format)
        if current_section and line and line.lower() not in ['_no response_', 'none', '']:
            if current_section == 'pr_numbers':
                # Handle PR numbers (comma-separated or single number)
                if ',' in line:
                    # Multiple comma-separated PRs
                    pr_list = [pr.strip() for pr in line.split(',') if pr.strip().isdigit()]
                    if pr_list:
                        pr_numbers = ','.join(pr_list)
                elif line.isdigit():
                    # Single PR number
                    pr_numbers = line

            elif current_section == 'release_pr':
                if line.isdigit():
                    release_pr = line

            elif current_section == 'required_approvals':
                if line.isdigit():
                    required_approvals = line

    return PRExtractionResult(pr_numbers, release_pr, required_approvals)


def main() -> int:
    """Main function to initialize merge queue with duplicate prevention."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    issue_body: str = GitHubUtils.get_env_var("ISSUE_BODY", "")
    repository: str = GitHubUtils.get_env_var("GITHUB_REPOSITORY")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    print("=== Merge Queue Initialization ===")
    print(f"Issue: #{issue_number}")
    print(f"Repository: {repository}")
    print("==================================")

    # Step 1: Extract PR information from issue body
    print("\n📋 Step 1: Extract PR Information")
    print("---------------------------------")

    pr_info = extract_pr_info_from_issue_body(issue_body)

    print(f"PR Numbers: {pr_info.pr_numbers}")
    print(f"Release PR: {pr_info.release_pr if pr_info.release_pr else '(none)'}")
    print(f"Required Approvals Override: {pr_info.required_approvals if pr_info.required_approvals else '(none)'}")

    # Step 2: Initialize tracking issue
    print("\n🚀 Step 2: Initialize Tracking Issue")
    print("------------------------------------")
    
    tracking_issue_number = initialize_tracking_issue(issue_number, pr_info.pr_numbers, pr_info.release_pr)
    
    if tracking_issue_number:
        print(f"✅ Tracking issue initialized: #{tracking_issue_number}")
        
        # Export tracking issue number and PR info for use in later workflow steps
        print("\n📤 Step 3: Export Information for Workflow")
        print("------------------------------------------")
        
        # Write to GitHub Actions output
        github_output = GitHubUtils.get_env_var("GITHUB_OUTPUT", "")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"tracking_issue_number={tracking_issue_number}\n")
                f.write(f"pr_numbers={pr_info.pr_numbers}\n")
                if pr_info.release_pr:
                    f.write(f"release_pr={pr_info.release_pr}\n")
                if pr_info.required_approvals:
                    f.write(f"required_approvals={pr_info.required_approvals}\n")
            print("✅ Information exported to GitHub Actions outputs")

        # Also write to temporary file as backup (for compatibility with existing scripts)
        with open("/tmp/tracking_issue.properties", "w") as f:
            f.write(f"TRACKING_ISSUE_NUMBER={tracking_issue_number}\n")
            f.write(f"PR_NUMBERS={pr_info.pr_numbers}\n")
            if pr_info.release_pr:
                f.write(f"RELEASE_PR={pr_info.release_pr}\n")
            if pr_info.required_approvals:
                f.write(f"REQUIRED_APPROVALS={pr_info.required_approvals}\n")

        # Also create the pr_extraction.properties file for compatibility
        with open("/tmp/pr_extraction.properties", "w") as f:
            f.write(f"EXTRACTED_PR_NUMBERS={pr_info.pr_numbers}\n")
            f.write(f"EXTRACTED_RELEASE_PR={pr_info.release_pr if pr_info.release_pr else ''}\n")
            f.write(f"EXTRACTED_REQUIRED_APPROVALS={pr_info.required_approvals if pr_info.required_approvals else ''}\n")

        print("✅ Information saved to temporary properties files")
        
        print("\n🎉 Merge Queue Initialization Complete!")
        print("======================================")
        print(f"✅ Tracking issue: #{tracking_issue_number}")
        print(f"✅ PR information: Extracted and exported")
        print(f"✅ Ready for next workflow steps")
        
        return 0
    else:
        print("❌ Failed to initialize tracking issue")
        return 1


if __name__ == "__main__":
    sys.exit(main())
