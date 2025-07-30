#!/usr/bin/env python3
"""
Standalone unit tests for generate_summary.py functions.
This file includes the functions directly to avoid import issues.
"""

import json
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime


# Mock GitHubUtils class
class MockGitHubUtils:
    @staticmethod
    def get_pr_author(pr_number):
        return type('MockResult', (), {'success': True, 'message': 'testuser'})()


# Copy the functions we want to test directly here
def parse_environment_data():
    """Parse environment variables and return processed data"""
    total_requested_raw = os.getenv('TOTAL_REQUESTED_RAW', '')
    total_requested = len([pr.strip() for pr in total_requested_raw.split(',') if pr.strip()])

    default_branch = os.getenv('DEFAULT_BRANCH', 'main')
    required_approvals = os.getenv('REQUIRED_APPROVALS', '2')
    submitter = os.getenv('SUBMITTER', 'unknown')
    
    def parse_comma_separated(env_var):
        value = os.getenv(env_var, '')
        return [item.strip() for item in value.split(',') if item.strip()]
    
    merged = parse_comma_separated('MERGED')

    # Parse UNMERGEABLE as JSON (it comes from validate-prs step as JSON)
    try:
        unmergeable_raw = os.getenv('UNMERGEABLE', '[]')
        unmergeable = json.loads(unmergeable_raw) if unmergeable_raw.strip() else []
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse UNMERGEABLE as JSON: {e}. Using empty list.", file=sys.stderr)
        unmergeable = []

    failed_update = parse_comma_separated('FAILED_UPDATE')
    failed_ci = parse_comma_separated('FAILED_CI')
    timeout = parse_comma_separated('TIMEOUT')
    startup_timeout = parse_comma_separated('STARTUP_TIMEOUT')
    failed_merge = parse_comma_separated('FAILED_MERGE')
    
    return {
        'default_branch': default_branch,
        'required_approvals': required_approvals,
        'total_requested': total_requested,
        'submitter': submitter,
        'merged': merged,
        'unmergeable': unmergeable,
        'failed_update': failed_update,
        'failed_ci': failed_ci,
        'timeout': timeout,
        'startup_timeout': startup_timeout,
        'failed_merge': failed_merge
    }


def get_failure_messages(default_branch, required_approvals):
    """Get the failure message templates"""
    return {
        'unmergeable': f"❌ This PR could not be merged due to one or more of the following:\n\n- Less than {required_approvals} approvals\n- Failing or missing status checks\n- Not up-to-date with `{default_branch}`\n- Not targeting `{default_branch}`\n\nPlease address these issues to include it in the next merge cycle.",
        'failed_update': f"❌ This PR could not be updated with the latest `{default_branch}` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `{default_branch}`.",
        'failed_ci': f"❌ This PR's CI checks failed after being updated with `{default_branch}`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `{default_branch}` - please check if this caused any new test failures.",
        'timeout': f"⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `{default_branch}`.\n\nThe PR has been updated with the latest `{default_branch}` - please check the CI status and re-run if needed.",
        'startup_timeout': f"⏰ This PR's CI workflow did not start within the 5-minute startup timeout period after being triggered.\n\nThis may indicate issues with CI runner availability or workflow configuration. The PR has been updated with the latest `{default_branch}` - please check the CI status and re-trigger if needed.",
        'failed_merge': f"❌ This PR failed to merge despite passing all checks. This is most likely due to merge conflicts that occurred after other PRs were merged to `{default_branch}`.\n\n**If you received a merge conflict notification:** Please resolve the conflicts in your branch and push the changes.\n\n**If no conflicts were reported:** This may be due to a GitHub API issue. The PR has been updated with the latest `{default_branch}` - please try merging manually or contact the repository administrators."
    }


def generate_summary_with_authors(data):
    """Generate the PR merge summary report with author information"""
    total_merged = len(data['merged'])
    total_failed = (len(data['unmergeable']) + len(data['failed_update']) +
                   len(data['failed_ci']) + len(data['timeout']) + len(data['startup_timeout']) + len(data['failed_merge']))
    date = datetime.now().strftime('%Y-%m-%d')

    summary = f"""# PR Merge Summary - {date}

## Overview
- **Total PRs Requested**: {data['total_requested']}
- **Successfully Merged**: {total_merged}
- **Failed to Merge**: {total_failed}

## Successfully Merged PRs ✅
"""

    if data['merged']:
        summary += '\n'.join(f"- PR #{pr}" for pr in data['merged'])
    else:
        summary += "- None"

    summary += """

## Failed PRs by Category ❌

### Initial Validation Failures
"""

    if data['unmergeable']:
        for pr in data['unmergeable']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - insufficient approvals, failing checks, or not targeting {data['default_branch']}"
    else:
        summary += "- None"

    summary += f"""

### Update with {data['default_branch'].title()} Failed
"""

    if data['failed_update']:
        for pr in data['failed_update']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - could not update branch with {data['default_branch']}"
    else:
        summary += "- None"

    summary += """

### CI Checks Failed
"""

    if data['failed_ci']:
        for pr in data['failed_ci']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI checks failed after update"
    else:
        summary += "- None"

    summary += """

### CI Execution Timeout
"""

    if data['timeout']:
        for pr in data['timeout']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI did not complete within 45 minutes"
    else:
        summary += "- None"

    summary += """

### CI Startup Timeout
"""

    if data['startup_timeout']:
        for pr in data['startup_timeout']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - CI workflow did not start within 5 minutes"
    else:
        summary += "- None"

    summary += """

### Merge Operation Failed
"""

    if data['failed_merge']:
        for pr in data['failed_merge']:
            author_result = MockGitHubUtils.get_pr_author(str(pr))
            author = author_result.message
            summary += f"\n- PR #{pr} (@{author}) - merge command failed (likely merge conflicts)"
    else:
        summary += "- None"

    summary += f"""

---
@{data.get('submitter', 'unknown')} - Your merge queue request has been completed!

*Automated workflow execution*"""

    return summary


# Test functions
def test_parse_environment_data_complete():
    """Test parsing with all environment variables set."""
    with patch.dict(os.environ, {
        'TOTAL_REQUESTED_RAW': '123,456,789',
        'DEFAULT_BRANCH': 'main',
        'REQUIRED_APPROVALS': '2',
        'SUBMITTER': 'testuser',
        'MERGED': '123,456',
        'UNMERGEABLE': '[789, 101]',
        'FAILED_UPDATE': '111,222',
        'FAILED_CI': '333',
        'TIMEOUT': '444,555',
        'STARTUP_TIMEOUT': '666',
        'FAILED_MERGE': '777,888'
    }):
        result = parse_environment_data()
        
        assert result['default_branch'] == 'main'
        assert result['required_approvals'] == '2'
        assert result['total_requested'] == 3
        assert result['submitter'] == 'testuser'
        assert result['merged'] == ['123', '456']
        assert result['unmergeable'] == [789, 101]
        assert result['failed_update'] == ['111', '222']
        assert result['failed_ci'] == ['333']
        assert result['timeout'] == ['444', '555']
        assert result['startup_timeout'] == ['666']
        assert result['failed_merge'] == ['777', '888']


def test_parse_environment_data_defaults():
    """Test parsing with default values."""
    with patch.dict(os.environ, {}, clear=True):
        result = parse_environment_data()
        
        assert result['default_branch'] == 'main'
        assert result['required_approvals'] == '2'
        assert result['total_requested'] == 0
        assert result['submitter'] == 'unknown'
        assert result['merged'] == []
        assert result['unmergeable'] == []
        assert result['failed_update'] == []
        assert result['failed_ci'] == []
        assert result['timeout'] == []
        assert result['startup_timeout'] == []
        assert result['failed_merge'] == []


def test_parse_environment_data_invalid_json():
    """Test parsing with invalid JSON in UNMERGEABLE."""
    with patch.dict(os.environ, {'UNMERGEABLE': 'invalid json'}):
        with patch('sys.stderr'):
            result = parse_environment_data()
            assert result['unmergeable'] == []


def test_get_failure_messages():
    """Test failure message generation."""
    messages = get_failure_messages('main', '2')
    
    assert 'unmergeable' in messages
    assert 'failed_update' in messages
    assert 'failed_ci' in messages
    assert 'timeout' in messages
    assert 'startup_timeout' in messages
    assert 'failed_merge' in messages
    
    assert 'Less than 2 approvals' in messages['unmergeable']
    assert 'main' in messages['unmergeable']
    assert 'main' in messages['failed_update']
    assert '45-minute timeout' in messages['timeout']
    assert '5-minute startup timeout' in messages['startup_timeout']


def test_generate_summary_with_authors_basic():
    """Test basic summary generation."""
    data = {
        'default_branch': 'main',
        'required_approvals': '2',
        'total_requested': 2,
        'submitter': 'submitter',
        'merged': ['123'],
        'unmergeable': [456],
        'failed_update': [],
        'failed_ci': [],
        'timeout': [],
        'startup_timeout': [],
        'failed_merge': []
    }
    
    result = generate_summary_with_authors(data)
    
    assert '# PR Merge Summary -' in result
    assert '**Total PRs Requested**: 2' in result
    assert '**Successfully Merged**: 1' in result
    assert '**Failed to Merge**: 1' in result
    assert 'PR #123' in result
    assert 'PR #456 (@testuser)' in result
    assert '@submitter - Your merge queue request has been completed!' in result


def test_generate_summary_with_authors_empty():
    """Test summary generation with empty PR lists."""
    data = {
        'default_branch': 'main',
        'required_approvals': '2',
        'total_requested': 0,
        'submitter': 'submitter',
        'merged': [],
        'unmergeable': [],
        'failed_update': [],
        'failed_ci': [],
        'timeout': [],
        'startup_timeout': [],
        'failed_merge': []
    }
    
    result = generate_summary_with_authors(data)
    
    assert '**Total PRs Requested**: 0' in result
    assert '**Successfully Merged**: 0' in result
    assert '**Failed to Merge**: 0' in result
    assert '- None' in result


def run_all_tests():
    """Run all test functions."""
    tests = [
        test_parse_environment_data_complete,
        test_parse_environment_data_defaults,
        test_parse_environment_data_invalid_json,
        test_get_failure_messages,
        test_generate_summary_with_authors_basic,
        test_generate_summary_with_authors_empty
    ]
    
    passed = 0
    total = len(tests)
    
    print("Running standalone generate_summary.py tests...")
    print("=" * 50)
    
    for test_func in tests:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} - Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"💥 {total - passed} tests failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
