"""
Unit tests for gh_utils.py module.
"""

import pytest
from unittest.mock import patch, MagicMock
import subprocess
import os
import sys

# Add the scripts directory to the path so we can import from common
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_utils import GitHubUtils, CommandResult, OperationResult


def test_command_result_creation():
    """Test CommandResult data class creation."""
    result = CommandResult(True, "output", "error")
    assert result.success is True
    assert result.stdout == "output"
    assert result.stderr == "error"


def test_operation_result_creation():
    """Test OperationResult data class creation."""
    result = OperationResult(True, "success message", "error details")
    assert result.success is True
    assert result.message == "success message"
    assert result.error_details == "error details"


def test_operation_result_optional_error():
    """Test OperationResult with optional error_details."""
    result = OperationResult(True, "success message")
    assert result.success is True
    assert result.message == "success message"
    assert result.error_details is None


def test_get_env_var_existing():
    """Test getting an existing environment variable."""
    with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
        result = GitHubUtils.get_env_var('TEST_VAR')
        assert result == 'test_value'


def test_get_env_var_with_default():
    """Test getting a non-existing environment variable with default."""
    result = GitHubUtils.get_env_var('NON_EXISTING_VAR', 'default_value')
    assert result == 'default_value'


def test_get_env_var_missing_no_default():
    """Test getting a non-existing environment variable without default."""
    with pytest.raises(ValueError) as exc_info:
        GitHubUtils.get_env_var('NON_EXISTING_VAR')
    assert "Required environment variable 'NON_EXISTING_VAR' is not set" in str(exc_info.value)


@patch('subprocess.run')
def test_run_gh_command_success(mock_subprocess_run):
    """Test successful command execution."""
    mock_result = MagicMock()
    mock_result.stdout = "test output"
    mock_result.stderr = "test error"
    mock_subprocess_run.return_value = mock_result

    result = GitHubUtils._run_gh_command(['--version'])

    assert isinstance(result, CommandResult)
    assert result.success is True
    assert result.stdout == "test output"
    assert result.stderr == "test error"
    mock_subprocess_run.assert_called_once()


@patch('subprocess.run')
def test_run_gh_command_failure(mock_subprocess_run):
    """Test failed command execution."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        1, ['gh', '--version'], output="output", stderr="error"
    )

    result = GitHubUtils._run_gh_command(['--version'])

    assert isinstance(result, CommandResult)
    assert result.success is False


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_pr_author_success(mock_run_gh_command):
    """Test successful PR author retrieval."""
    mock_command_result = CommandResult(True, "testuser", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_pr_author("123")

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert result.message == "testuser"
    assert result.error_details is None


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_pr_author_failure(mock_run_gh_command):
    """Test failed PR author retrieval."""
    mock_command_result = CommandResult(False, "", "API error")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_pr_author("123")

    assert isinstance(result, OperationResult)
    assert result.success is False
    assert result.message == "unknown"
    assert result.error_details is not None


@patch.object(GitHubUtils, '_run_gh_command')
def test_comment_on_pr_success(mock_run_gh_command):
    """Test successful PR commenting."""
    mock_command_result = CommandResult(True, "comment created", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.comment_on_pr("123", "test comment")

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert "Commented on PR #123" in result.message


@patch.object(GitHubUtils, '_run_gh_command')
def test_update_pr_branch_success(mock_run_gh_command):
    """Test successful PR branch update."""
    mock_command_result = CommandResult(True, "updated", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.update_pr_branch("123")

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert "Updated PR #123" in result.message


@patch.object(GitHubUtils, '_run_gh_command')
def test_search_issue_with_all_params(mock_run_gh_command):
    """Test issue search with all parameters."""
    mock_command_result = CommandResult(True, '[]', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.search_issue(
        label="bug",
        state="open",
        search="test",
        json_fields="number,title"
    )

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify the command was called with correct arguments
    mock_run_gh_command.assert_called_once()
    args = mock_run_gh_command.call_args[0][0]
    assert "--label" in args
    assert "bug" in args
    assert "--state" in args
    assert "open" in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_add_comment_success(mock_run_gh_command):
    """Test successful comment addition."""
    mock_command_result = CommandResult(True, "comment added", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.add_comment("123", "test comment")

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert "Added comment to issue #123" in result.message


@patch.object(GitHubUtils, '_run_gh_command')
def test_create_issue_success(mock_run_gh_command):
    """Test successful issue creation."""
    mock_command_result = CommandResult(True, "https://github.com/owner/repo/issues/123", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.create_issue("Test Issue", "Test body", "bug")

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify the command was called with correct arguments
    mock_run_gh_command.assert_called_once()
    args = mock_run_gh_command.call_args[0][0]
    assert "--title" in args
    assert "Test Issue" in args
    assert "--label" in args
    assert "bug" in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_create_label_success(mock_run_gh_command):
    """Test successful label creation."""
    mock_command_result = CommandResult(True, "label created", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.create_label("bug", "Bug reports")

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert "✅ Created label 'bug'" == result.message


@patch.object(GitHubUtils, '_run_gh_command')
def test_create_label_already_exists(mock_run_gh_command):
    """Test label creation when label already exists."""
    mock_command_result = CommandResult(False, "", "already exists")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.create_label("bug", "Bug reports")

    assert isinstance(result, OperationResult)
    assert result.success is True  # Should be success when already exists
    assert "already exists" in result.message


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_workflow_run_status_success(mock_run_gh_command):
    """Test successful workflow run status retrieval."""
    mock_command_result = CommandResult(True, '{"status": "completed", "conclusion": "success"}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_workflow_run_status("12345")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "run", "view", "12345", "--json", "status,conclusion,workflowName"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_comment_timestamp_success(mock_run_gh_command):
    """Test successful comment timestamp retrieval."""
    mock_command_result = CommandResult(True, '{"created_at": "2023-01-01T00:00:00Z"}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_comment_timestamp("12345")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "api", "repos/:owner/:repo/issues/comments/12345"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_merge_pr_basic(mock_run_gh_command):
    """Test basic PR merge."""
    mock_command_result = CommandResult(True, "merged", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.merge_pr("123")

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify default parameters
    args = mock_run_gh_command.call_args[0][0]
    assert "--squash" in args
    assert "--delete-branch" not in args
    assert "--admin" not in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_merge_pr_with_all_options(mock_run_gh_command):
    """Test PR merge with all options."""
    mock_command_result = CommandResult(True, "merged", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.merge_pr(
        "123",
        squash=True,
        delete_branch=True,
        merge_message="Custom message",
        admin=True
    )

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify all options are included
    args = mock_run_gh_command.call_args[0][0]
    assert "--squash" in args
    assert "--delete-branch" in args
    assert "--admin" in args
    assert "--subject" in args
    assert "Custom message" in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_trigger_ci_comment_default(mock_run_gh_command):
    """Test CI trigger comment with default text."""
    mock_command_result = CommandResult(True, "https://github.com/owner/repo/issues/123#issuecomment-456", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.trigger_ci_comment("123")

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify default comment text
    args = mock_run_gh_command.call_args[0][0]
    assert "Ok to test" in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_trigger_ci_comment_custom(mock_run_gh_command):
    """Test CI trigger comment with custom text."""
    mock_command_result = CommandResult(True, "comment created", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.trigger_ci_comment("123", "Custom trigger")

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify custom comment text
    args = mock_run_gh_command.call_args[0][0]
    assert "Custom trigger" in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_branch_protection_success(mock_run_gh_command):
    """Test successful branch protection retrieval."""
    mock_command_result = CommandResult(True, '{"required_pull_request_reviews": {"required_approving_review_count": 2}}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_branch_protection("owner/repo", "main")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "api", "repos/owner/repo/branches/main/protection"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_pr_details_success(mock_run_gh_command):
    """Test successful PR details retrieval."""
    mock_command_result = CommandResult(True, '{"state": "OPEN", "author": {"login": "testuser"}}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_pr_details("123", "state,author")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "pr", "view", "123", "--json", "state,author"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_pr_comments_success(mock_run_gh_command):
    """Test successful PR comments retrieval."""
    mock_command_result = CommandResult(True, '{"comments": []}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_pr_comments("123")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "pr", "view", "123", "--json", "comments"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_get_pr_branch_name_success(mock_run_gh_command):
    """Test successful PR branch name retrieval."""
    mock_command_result = CommandResult(True, '{"headRefName": "feature-branch"}', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.get_pr_branch_name("123")

    assert isinstance(result, CommandResult)
    assert result.success is True
    mock_run_gh_command.assert_called_once_with([
        "pr", "view", "123", "--json", "headRefName"
    ], check=False)


@patch.object(GitHubUtils, '_run_gh_command')
def test_search_issue_no_params(mock_run_gh_command):
    """Test issue search with no parameters."""
    mock_command_result = CommandResult(True, '[]', "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.search_issue()

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify only basic command is called
    args = mock_run_gh_command.call_args[0][0]
    assert args == ["issue", "list"]


@patch.object(GitHubUtils, '_run_gh_command')
def test_create_issue_no_label(mock_run_gh_command):
    """Test issue creation without label."""
    mock_command_result = CommandResult(True, "issue created", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.create_issue("Test Issue", "Test body")

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify no label is included
    args = mock_run_gh_command.call_args[0][0]
    assert "--label" not in args


@patch.object(GitHubUtils, '_run_gh_command')
def test_merge_pr_no_squash(mock_run_gh_command):
    """Test PR merge without squash."""
    mock_command_result = CommandResult(True, "merged", "")
    mock_run_gh_command.return_value = mock_command_result

    result = GitHubUtils.merge_pr("123", squash=False)

    assert isinstance(result, CommandResult)
    assert result.success is True
    # Verify squash is not included
    args = mock_run_gh_command.call_args[0][0]
    assert "--squash" not in args



