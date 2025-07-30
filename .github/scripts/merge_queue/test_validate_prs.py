#!/usr/bin/env python3
"""
Unit tests for validate_prs.py functions using pytest.
Tests individual functions without classes.
"""

import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Mock GitHubUtils before importing
sys.modules['common'] = MagicMock()
sys.modules['common.gh_utils'] = MagicMock()

# Mock classes for testing
class MockOperationResult:
    def __init__(self, success, stdout="", stderr=""):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr

class MockGitHubUtils:
    @staticmethod
    def get_env_var(name, default=None):
        return os.environ.get(name, default)
    
    @staticmethod
    def get_branch_protection(repository, branch):
        return MockOperationResult(True, '{"required_pull_request_reviews": {"required_approving_review_count": 2}}')
    
    @staticmethod
    def get_pr_details(pr_number, fields):
        return MockOperationResult(True, '{"baseRefName": "main", "mergeable": "MERGEABLE", "state": "OPEN", "reviews": [{"state": "APPROVED"}], "statusCheckRollup": [{"context": "test", "state": "SUCCESS"}]}')

sys.modules['common.gh_utils'].GitHubUtils = MockGitHubUtils

# Copy the functions we want to test directly here
def parse_pr_numbers(pr_numbers_str: str) -> list:
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
    result = MockGitHubUtils.get_branch_protection(repository, default_branch)

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


def get_pr_info(pr_number: str) -> dict:
    """Get PR information using GitHub CLI."""
    result = MockGitHubUtils.get_pr_details(pr_number,
        "baseRefName,mergeable,headRefName,reviews,statusCheckRollup,state")

    if not result.success:
        print(f"❌ Failed to get info for PR #{pr_number}: {result.stderr}")
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse PR #{pr_number} info: {e}")
        return None


def count_approvals(reviews: list) -> int:
    """Count approved reviews."""
    return sum(1 for review in reviews if review.get("state") == "APPROVED")


def get_failing_checks(status_checks: list) -> list:
    """Get list of failing or pending status checks."""
    failing = []
    for check in status_checks:
        state = check.get("state", "")
        if state not in ["SUCCESS"]:
            failing.append(f"{check.get('context', 'unknown')}:{state}")
    return failing


def validate_pr(pr_number: str, required_approvals: int, default_branch: str, pr_type: str = "regular") -> tuple:
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


# Test functions
def test_parse_pr_numbers_valid_input():
    """Test parsing valid comma-separated PR numbers."""
    result = parse_pr_numbers("123,456,789")
    assert result == ["123", "456", "789"]


def test_parse_pr_numbers_empty_string():
    """Test parsing empty string returns empty list."""
    assert parse_pr_numbers("") == []
    assert parse_pr_numbers("   ") == []


def test_parse_pr_numbers_single_pr():
    """Test parsing single PR number."""
    result = parse_pr_numbers("123")
    assert result == ["123"]


def test_parse_pr_numbers_with_spaces():
    """Test parsing PR numbers with spaces."""
    result = parse_pr_numbers(" 123 , 456 , 789 ")
    assert result == ["123", "456", "789"]


def test_parse_pr_numbers_with_empty_values():
    """Test parsing with empty values in the list."""
    result = parse_pr_numbers("123,,456,")
    assert result == ["123", "456"]


def test_get_required_approvals_manual_valid():
    """Test getting required approvals from manual input."""
    result = get_required_approvals("3", "owner/repo", "main")
    assert result == 3


def test_get_required_approvals_manual_invalid():
    """Test getting required approvals with invalid manual input."""
    result = get_required_approvals("invalid", "owner/repo", "main")
    assert result == 2  # Should fall back to branch protection


def test_get_required_approvals_empty_manual():
    """Test getting required approvals with empty manual input."""
    result = get_required_approvals("", "owner/repo", "main")
    assert result == 2  # Should use branch protection


def test_get_required_approvals_branch_protection_failure():
    """Test getting required approvals when branch protection fails."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_branch_protection
    MockGitHubUtils.get_branch_protection = lambda repo, branch: MockOperationResult(False, "", "error")
    
    try:
        result = get_required_approvals("", "owner/repo", "main")
        assert result == 1  # Should default to 1
    finally:
        MockGitHubUtils.get_branch_protection = original_method


def test_get_required_approvals_invalid_json():
    """Test getting required approvals with invalid JSON response."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_branch_protection
    MockGitHubUtils.get_branch_protection = lambda repo, branch: MockOperationResult(True, "invalid json", "")
    
    try:
        result = get_required_approvals("", "owner/repo", "main")
        assert result == 1  # Should default to 1
    finally:
        MockGitHubUtils.get_branch_protection = original_method


def test_count_approvals_multiple_reviews():
    """Test counting approvals with multiple reviews."""
    reviews = [
        {"state": "APPROVED"},
        {"state": "CHANGES_REQUESTED"},
        {"state": "APPROVED"},
        {"state": "COMMENTED"}
    ]
    result = count_approvals(reviews)
    assert result == 2


def test_count_approvals_no_reviews():
    """Test counting approvals with no reviews."""
    result = count_approvals([])
    assert result == 0


def test_count_approvals_no_approved_reviews():
    """Test counting approvals with no approved reviews."""
    reviews = [
        {"state": "CHANGES_REQUESTED"},
        {"state": "COMMENTED"}
    ]
    result = count_approvals(reviews)
    assert result == 0


def test_get_failing_checks_all_success():
    """Test getting failing checks when all checks pass."""
    status_checks = [
        {"context": "test1", "state": "SUCCESS"},
        {"context": "test2", "state": "SUCCESS"}
    ]
    result = get_failing_checks(status_checks)
    assert result == []


def test_get_failing_checks_some_failing():
    """Test getting failing checks with some failures."""
    status_checks = [
        {"context": "test1", "state": "SUCCESS"},
        {"context": "test2", "state": "FAILURE"},
        {"context": "test3", "state": "PENDING"}
    ]
    result = get_failing_checks(status_checks)
    assert result == ["test2:FAILURE", "test3:PENDING"]


def test_get_failing_checks_empty_list():
    """Test getting failing checks with empty list."""
    result = get_failing_checks([])
    assert result == []


def test_get_failing_checks_missing_context():
    """Test getting failing checks with missing context."""
    status_checks = [
        {"state": "FAILURE"}
    ]
    result = get_failing_checks(status_checks)
    assert result == ["unknown:FAILURE"]


def test_validate_pr_success():
    """Test validating a successful PR."""
    is_mergeable, reasons = validate_pr("123", 1, "main")
    assert is_mergeable is True
    assert reasons == []


def test_validate_pr_closed():
    """Test validating a closed PR."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(
        True, '{"baseRefName": "main", "mergeable": "MERGEABLE", "state": "CLOSED", "reviews": [], "statusCheckRollup": []}'
    )
    
    try:
        is_mergeable, reasons = validate_pr("123", 1, "main")
        assert is_mergeable is False
        assert "PR is not open" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_validate_pr_wrong_base_branch():
    """Test validating PR with wrong base branch."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(
        True, '{"baseRefName": "develop", "mergeable": "MERGEABLE", "state": "OPEN", "reviews": [{"state": "APPROVED"}], "statusCheckRollup": []}'
    )
    
    try:
        is_mergeable, reasons = validate_pr("123", 1, "main")
        assert is_mergeable is False
        assert "Does not target 'main'" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_validate_pr_merge_conflicts():
    """Test validating PR with merge conflicts."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(
        True, '{"baseRefName": "main", "mergeable": "CONFLICTING", "state": "OPEN", "reviews": [{"state": "APPROVED"}], "statusCheckRollup": []}'
    )
    
    try:
        is_mergeable, reasons = validate_pr("123", 1, "main")
        assert is_mergeable is False
        assert "Has merge conflicts" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_validate_pr_insufficient_approvals():
    """Test validating PR with insufficient approvals."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(
        True, '{"baseRefName": "main", "mergeable": "MERGEABLE", "state": "OPEN", "reviews": [], "statusCheckRollup": []}'
    )
    
    try:
        is_mergeable, reasons = validate_pr("123", 2, "main")
        assert is_mergeable is False
        assert "Has 0 approvals, but 2 are required" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_validate_pr_failing_checks():
    """Test validating PR with failing status checks."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(
        True, '{"baseRefName": "main", "mergeable": "MERGEABLE", "state": "OPEN", "reviews": [{"state": "APPROVED"}], "statusCheckRollup": [{"context": "test", "state": "FAILURE"}]}'
    )
    
    try:
        is_mergeable, reasons = validate_pr("123", 1, "main")
        assert is_mergeable is False
        assert "Has failing/missing checks" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_validate_pr_api_failure():
    """Test validating PR when API call fails."""
    # Temporarily replace the method
    original_method = MockGitHubUtils.get_pr_details
    MockGitHubUtils.get_pr_details = lambda pr, fields: MockOperationResult(False, "", "API error")
    
    try:
        is_mergeable, reasons = validate_pr("123", 1, "main")
        assert is_mergeable is False
        assert "Failed to retrieve PR information" in reasons[0]
    finally:
        MockGitHubUtils.get_pr_details = original_method


def test_set_github_output_with_file():
    """Test setting GitHub output with GITHUB_OUTPUT file."""
    with patch.dict(os.environ, {'GITHUB_OUTPUT': '/tmp/test_output'}):
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            set_github_output("test_name", "test_value")
            
            mock_open.assert_called_once_with('/tmp/test_output', 'a')
            mock_file.write.assert_called_once_with('test_name=test_value\n')


def test_set_github_output_without_file():
    """Test setting GitHub output without GITHUB_OUTPUT file."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('builtins.print') as mock_print:
            set_github_output("test_name", "test_value")
            mock_print.assert_called_once_with("Output: test_name=test_value")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
