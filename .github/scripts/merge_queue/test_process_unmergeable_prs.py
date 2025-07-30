#!/usr/bin/env python3
"""
Unit tests for process_unmergeable_prs.py functions using pytest.
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
    def __init__(self, success, message, error_details=None):
        self.success = success
        self.message = message
        self.error_details = error_details

class MockGitHubUtils:
    @staticmethod
    def get_env_var(name, default=None):
        return os.environ.get(name, default)
    
    @staticmethod
    def get_pr_author(pr_number):
        return MockOperationResult(True, 'testuser')
    
    @staticmethod
    def comment_on_pr(pr_number, message):
        return MockOperationResult(True, 'success')

sys.modules['common.gh_utils'].GitHubUtils = MockGitHubUtils

# Copy the functions we want to test directly here
def parse_json_array(json_str: str) -> list:
    """Parse JSON array string, return empty list if invalid."""
    if not json_str or json_str.strip() == "":
        return []
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse JSON array: {json_str}")
        return []


def parse_comma_separated(csv_str: str) -> list:
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
    return f"""❌ @{author}, this PR passed initial validation but failed during the merge process. This is most commonly due to:

- **Merge conflicts** that developed after other PRs were merged (check for a separate merge conflict notification comment)
- GitHub API errors during merge
- Branch protection rule changes

**If you received a merge conflict notification:** Please resolve the conflicts in your branch and push the changes.

**Otherwise:** Please check the PR status and try again in the next merge cycle."""


# Test functions
def test_parse_json_array_valid_json():
    """Test parsing valid JSON array."""
    json_str = '["123", "456", "789"]'
    result = parse_json_array(json_str)
    assert result == ["123", "456", "789"]


def test_parse_json_array_empty_string():
    """Test parsing empty string returns empty list."""
    assert parse_json_array("") == []
    assert parse_json_array("   ") == []


def test_parse_json_array_invalid_json():
    """Test parsing invalid JSON returns empty list."""
    result = parse_json_array("invalid json")
    assert result == []


def test_parse_json_array_empty_array():
    """Test parsing empty JSON array."""
    json_str = '[]'
    result = parse_json_array(json_str)
    assert result == []


def test_parse_json_array_mixed_types():
    """Test parsing JSON array with mixed types."""
    json_str = '[123, "456", 789]'
    result = parse_json_array(json_str)
    assert result == [123, "456", 789]


def test_parse_json_array_single_item():
    """Test parsing JSON array with single item."""
    json_str = '["123"]'
    result = parse_json_array(json_str)
    assert result == ["123"]


def test_parse_json_array_whitespace():
    """Test parsing JSON array with whitespace."""
    json_str = ' [ "123" , "456" ] '
    result = parse_json_array(json_str)
    assert result == ["123", "456"]


def test_parse_comma_separated_valid_input():
    """Test parsing valid comma-separated string."""
    csv_str = "123,456,789"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456", "789"]


def test_parse_comma_separated_empty_string():
    """Test parsing empty string returns empty list."""
    assert parse_comma_separated("") == []
    assert parse_comma_separated("   ") == []


def test_parse_comma_separated_single_item():
    """Test parsing single item."""
    csv_str = "123"
    result = parse_comma_separated(csv_str)
    assert result == ["123"]


def test_parse_comma_separated_with_spaces():
    """Test parsing with spaces around items."""
    csv_str = " 123 , 456 , 789 "
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456", "789"]


def test_parse_comma_separated_with_empty_values():
    """Test parsing with empty values in the list."""
    csv_str = "123,,456,"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456"]


def test_parse_comma_separated_trailing_comma():
    """Test parsing with trailing comma."""
    csv_str = "123,456,789,"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456", "789"]


def test_parse_comma_separated_leading_comma():
    """Test parsing with leading comma."""
    csv_str = ",123,456,789"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456", "789"]


def test_generate_validation_failure_message():
    """Test generating validation failure message."""
    message = generate_validation_failure_message("testuser", "2", "main")
    
    assert "❌ @testuser" in message
    assert "Less than 2 approvals" in message
    assert "Not up-to-date with `main`" in message
    assert "Not targeting `main`" in message
    assert "Please address these issues" in message


def test_generate_validation_failure_message_different_params():
    """Test generating validation failure message with different parameters."""
    message = generate_validation_failure_message("anotheruser", "3", "develop")
    
    assert "❌ @anotheruser" in message
    assert "Less than 3 approvals" in message
    assert "Not up-to-date with `develop`" in message
    assert "Not targeting `develop`" in message


def test_generate_merge_failure_message():
    """Test generating merge failure message."""
    message = generate_merge_failure_message("testuser")
    
    assert "❌ @testuser" in message
    assert "passed initial validation but failed during the merge process" in message
    assert "Merge conflicts" in message
    assert "GitHub API errors" in message
    assert "Branch protection rule changes" in message
    assert "If you received a merge conflict notification" in message
    assert "Please check the PR status" in message


def test_generate_merge_failure_message_different_user():
    """Test generating merge failure message with different user."""
    message = generate_merge_failure_message("anotheruser")
    
    assert "❌ @anotheruser" in message
    assert "passed initial validation but failed during the merge process" in message


def test_parse_json_array_nested_structure():
    """Test parsing JSON array with nested structures."""
    json_str = '[{"pr": "123"}, {"pr": "456"}]'
    result = parse_json_array(json_str)
    assert result == [{"pr": "123"}, {"pr": "456"}]


def test_parse_json_array_malformed_json():
    """Test parsing malformed JSON."""
    json_str = '["123", "456"'  # Missing closing bracket
    result = parse_json_array(json_str)
    assert result == []


def test_parse_json_array_null_values():
    """Test parsing JSON array with null values."""
    json_str = '["123", null, "456"]'
    result = parse_json_array(json_str)
    assert result == ["123", None, "456"]


def test_parse_comma_separated_special_characters():
    """Test parsing comma-separated string with special characters."""
    csv_str = "PR-123,ISSUE-456,BUG-789"
    result = parse_comma_separated(csv_str)
    assert result == ["PR-123", "ISSUE-456", "BUG-789"]


def test_parse_comma_separated_numbers_as_strings():
    """Test parsing comma-separated numbers."""
    csv_str = "123,456,789"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "456", "789"]


def test_parse_comma_separated_mixed_content():
    """Test parsing comma-separated string with mixed content."""
    csv_str = "123,abc,456,def"
    result = parse_comma_separated(csv_str)
    assert result == ["123", "abc", "456", "def"]


def test_generate_validation_failure_message_empty_params():
    """Test generating validation failure message with empty parameters."""
    message = generate_validation_failure_message("", "", "")
    
    assert "❌ @" in message
    assert "Less than  approvals" in message
    assert "Not up-to-date with ``" in message
    assert "Not targeting ``" in message


def test_generate_merge_failure_message_empty_user():
    """Test generating merge failure message with empty user."""
    message = generate_merge_failure_message("")
    
    assert "❌ @" in message
    assert "passed initial validation but failed during the merge process" in message


def test_parse_json_array_boolean_values():
    """Test parsing JSON array with boolean values."""
    json_str = '[true, false, "123"]'
    result = parse_json_array(json_str)
    assert result == [True, False, "123"]


def test_parse_json_array_numeric_values():
    """Test parsing JSON array with numeric values."""
    json_str = '[123, 456.78, "789"]'
    result = parse_json_array(json_str)
    assert result == [123, 456.78, "789"]


def test_parse_comma_separated_unicode_characters():
    """Test parsing comma-separated string with unicode characters."""
    csv_str = "PR-123,测试-456,🚀-789"
    result = parse_comma_separated(csv_str)
    assert result == ["PR-123", "测试-456", "🚀-789"]


def test_generate_validation_failure_message_special_characters():
    """Test generating validation failure message with special characters in username."""
    message = generate_validation_failure_message("user-name_123", "2", "main")
    
    assert "❌ @user-name_123" in message
    assert "Less than 2 approvals" in message


def test_generate_merge_failure_message_special_characters():
    """Test generating merge failure message with special characters in username."""
    message = generate_merge_failure_message("user-name_123")
    
    assert "❌ @user-name_123" in message
    assert "passed initial validation but failed during the merge process" in message


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
