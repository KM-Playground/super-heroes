#!/usr/bin/env python3
"""
Extract PR information from GitHub issue body.

This script parses the issue body from a GitHub issue form to extract
PR numbers, release PR, and required approvals override.
"""

import json
import os
import sys
from typing import Optional, Tuple

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.gh_utils import GitHubUtils


def parse_issue_form_field(lines: list[str], field_header: str) -> Optional[str]:
    """
    Parse a specific field from GitHub issue form format.
    
    Args:
        lines: List of lines from the issue body
        field_header: The header to look for (e.g., "### PR Numbers")
    
    Returns:
        The field value or None if not found/empty
    """
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        if line_stripped == field_header:
            # Look for the value in the next few lines
            for j in range(i + 1, min(i + 10, len(lines))):
                value_line = lines[j].strip()
                
                # Skip empty lines
                if not value_line:
                    continue
                
                # Stop if we hit another section header
                if value_line.startswith('###'):
                    break
                
                # Skip the "No response" placeholder
                if value_line == '_No response_':
                    break
                
                # Found a value
                return value_line
    
    return None


def clean_field_value(value: Optional[str]) -> str:
    """
    Clean and validate a field value.
    
    Args:
        value: Raw field value from issue form
    
    Returns:
        Cleaned string value (empty string if None or invalid)
    """
    if not value:
        return ""
    
    # Remove markdown formatting and extra whitespace
    cleaned = value.replace('`', '').replace('*', '').replace('_', '').strip()
    return cleaned


def extract_pr_information(issue_body: str) -> Tuple[str, str, str]:
    """
    Extract PR information from GitHub issue form body.
    
    Args:
        issue_body: The raw issue body text
    
    Returns:
        Tuple of (pr_numbers, release_pr, required_approvals)
    """
    print("Extracting PR information from issue body...")
    print(f"Issue body length: {len(issue_body)}")
    print(f"Issue body preview: {issue_body[:500]}...")
    
    # Split into lines for parsing
    lines = issue_body.split('\n')
    
    # Debug: Print all lines with numbers
    print("\nAll lines:")
    for i, line in enumerate(lines):
        print(f"Line {i}: \"{line}\"")
    
    # Extract each field
    pr_numbers_raw = parse_issue_form_field(lines, "### PR Numbers")
    release_pr_raw = parse_issue_form_field(lines, "### Release PR (Optional)")
    required_approvals_raw = parse_issue_form_field(lines, "### Required Approvals Override (Optional)")
    
    # Clean the values
    pr_numbers = clean_field_value(pr_numbers_raw)
    release_pr = clean_field_value(release_pr_raw)
    required_approvals = clean_field_value(required_approvals_raw)
    
    print(f"\nExtracted values:")
    print(f"PR Numbers (raw): '{pr_numbers_raw}'")
    print(f"PR Numbers (clean): '{pr_numbers}'")
    print(f"Release PR (raw): '{release_pr_raw}'")
    print(f"Release PR (clean): '{release_pr}'")
    print(f"Required Approvals (raw): '{required_approvals_raw}'")
    print(f"Required Approvals (clean): '{required_approvals}'")
    
    return pr_numbers, release_pr, required_approvals


def validate_pr_numbers(pr_numbers: str) -> bool:
    """
    Validate that PR numbers are provided and in correct format.
    
    Args:
        pr_numbers: Comma-separated PR numbers string
    
    Returns:
        True if valid, False otherwise
    """
    if not pr_numbers:
        return False
    
    # Check if it contains numbers and commas
    # Basic validation - should contain digits and optionally commas
    import re
    pattern = r'^[\d,\s]+$'
    return bool(re.match(pattern, pr_numbers))


def post_error_comment(issue_number: int, error_message: str) -> None:
    """Post an error comment to the issue."""
    full_message = f"""❌ **Error**: {error_message}

**Common Issues:**
• Make sure the PR Numbers field is filled with comma-separated numbers (e.g., `123,124,125`)
• Ensure you're using the correct issue template
• Check that all required fields are properly completed

**To Fix**: Edit the issue description or create a new issue with the correct information."""
    
    result = GitHubUtils.comment_on_pr(str(issue_number), full_message)
    if result.success:
        print("✅ Posted error comment to issue")
    else:
        print(f"⚠️ Failed to post error comment: {result.error_details}")


def export_environment_variables(pr_numbers: str, release_pr: str, required_approvals: str) -> None:
    """Export extracted values as environment variables."""
    # Set environment variables for the current process and child processes
    os.environ['EXTRACTED_PR_NUMBERS'] = pr_numbers
    os.environ['EXTRACTED_RELEASE_PR'] = release_pr
    os.environ['EXTRACTED_REQUIRED_APPROVALS'] = required_approvals

    # Also write to GITHUB_ENV for GitHub Actions workflow steps
    github_env = os.environ.get('GITHUB_ENV')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f"EXTRACTED_PR_NUMBERS={pr_numbers}\n")
            f.write(f"EXTRACTED_RELEASE_PR={release_pr}\n")
            f.write(f"EXTRACTED_REQUIRED_APPROVALS={required_approvals}\n")
        print("✅ Exported values as environment variables for workflow")
    else:
        print("⚠️ GITHUB_ENV not found, variables only set for current process")

    # Print the exported values for verification
    print(f"✅ Exported environment variables:")
    print(f"   EXTRACTED_PR_NUMBERS={pr_numbers}")
    print(f"   EXTRACTED_RELEASE_PR={release_pr}")
    print(f"   EXTRACTED_REQUIRED_APPROVALS={required_approvals}")


def main() -> int:
    """Main function to extract PR information."""
    # Get environment variables
    issue_number_str: str = GitHubUtils.get_env_var("ISSUE_NUMBER")
    issue_body: str = GitHubUtils.get_env_var("ISSUE_BODY")
    
    # Convert issue number to int
    try:
        issue_number: int = int(issue_number_str)
    except ValueError:
        print(f"❌ Invalid issue number: {issue_number_str}")
        return 1
    
    print("=== PR Information Extraction ===")
    print(f"Issue: #{issue_number}")
    print("==================================")
    
    # Extract PR information
    pr_numbers, release_pr, required_approvals = extract_pr_information(issue_body)
    
    # Validate PR numbers (required field)
    if not validate_pr_numbers(pr_numbers):
        error_msg = "Could not extract PR numbers from the issue. Please ensure the PR Numbers field is properly filled."
        print(f"❌ {error_msg}")
        post_error_comment(issue_number, error_msg)
        return 1
    
    # Export values as environment variables
    export_environment_variables(pr_numbers, release_pr, required_approvals)
    
    print("✅ Successfully extracted PR information")
    print(f"   PR Numbers: {pr_numbers}")
    print(f"   Release PR: {release_pr if release_pr else '(none)'}")
    print(f"   Required Approvals: {required_approvals if required_approvals else '(none)'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
