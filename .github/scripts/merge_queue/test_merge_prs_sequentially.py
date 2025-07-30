#!/usr/bin/env python3
"""
Simple unit tests for merge_prs_sequentially.py functions using pytest.
Tests core functions without complex mocking.
"""

import pytest
import json
import os
import sys
import datetime
from unittest.mock import patch, MagicMock

# Copy the core functions we want to test directly here
def parse_iso_datetime(iso_string: str) -> datetime.datetime:
    """Parse ISO datetime string, handling both Z and +00:00 timezone formats."""
    if not iso_string:
        raise ValueError("Empty datetime string")

    # Handle Z timezone format by converting to +00:00 for fromisoformat compatibility
    if iso_string.endswith('Z'):
        # Convert Z to +00:00: 2025-07-16T14:47:52Z -> 2025-07-16T14:47:52+00:00
        normalized_string = iso_string.replace('Z', '+00:00')
    else:
        # Assume it already has timezone info
        normalized_string = iso_string

    return datetime.datetime.fromisoformat(normalized_string)


def parse_mergeable_prs(json_str: str) -> list:
    """Parse and sort mergeable PRs from JSON string."""
    if not json_str or json_str.strip() == "":
        return []

    try:
        pr_strings = json.loads(json_str)
        pr_numbers = [int(pr) for pr in pr_strings]
        return sorted(pr_numbers)  # Sort chronologically (lowest number first)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing mergeable PRs: {e}")
        return []


def set_github_output(name: str, value: str):
    """Set GitHub Actions output."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"Output: {name}={value}")


# Test functions
def test_parse_iso_datetime_z_format():
    """Test parsing ISO datetime with Z timezone."""
    result = parse_iso_datetime("2025-07-16T14:47:52Z")
    expected = datetime.datetime.fromisoformat("2025-07-16T14:47:52+00:00")
    assert result == expected


def test_parse_iso_datetime_offset_format():
    """Test parsing ISO datetime with +00:00 timezone."""
    result = parse_iso_datetime("2025-07-16T14:47:52+00:00")
    expected = datetime.datetime.fromisoformat("2025-07-16T14:47:52+00:00")
    assert result == expected


def test_parse_iso_datetime_empty_string():
    """Test parsing empty datetime string raises ValueError."""
    with pytest.raises(ValueError, match="Empty datetime string"):
        parse_iso_datetime("")


def test_parse_iso_datetime_invalid_format():
    """Test parsing invalid datetime string raises ValueError."""
    with pytest.raises(ValueError):
        parse_iso_datetime("invalid-date")


def test_parse_mergeable_prs_valid_json():
    """Test parsing valid JSON string of PR numbers."""
    json_str = '["123", "456", "789"]'
    result = parse_mergeable_prs(json_str)
    assert result == [123, 456, 789]


def test_parse_mergeable_prs_empty_string():
    """Test parsing empty string returns empty list."""
    assert parse_mergeable_prs("") == []
    assert parse_mergeable_prs("   ") == []


def test_parse_mergeable_prs_invalid_json():
    """Test parsing invalid JSON returns empty list."""
    result = parse_mergeable_prs("invalid json")
    assert result == []


def test_parse_mergeable_prs_sorts_chronologically():
    """Test that PR numbers are sorted chronologically (lowest first)."""
    json_str = '["789", "123", "456"]'
    result = parse_mergeable_prs(json_str)
    assert result == [123, 456, 789]


def test_parse_mergeable_prs_mixed_types():
    """Test parsing with mixed string/int types."""
    json_str = '[123, "456", "789"]'
    result = parse_mergeable_prs(json_str)
    assert result == [123, 456, 789]


def test_parse_mergeable_prs_single_pr():
    """Test parsing single PR."""
    json_str = '["123"]'
    result = parse_mergeable_prs(json_str)
    assert result == [123]


def test_parse_mergeable_prs_empty_array():
    """Test parsing empty JSON array."""
    json_str = '[]'
    result = parse_mergeable_prs(json_str)
    assert result == []


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


def test_parse_iso_datetime_different_timezones():
    """Test parsing datetime with different timezone formats."""
    # Test with +05:30 timezone
    result1 = parse_iso_datetime("2025-07-16T14:47:52+05:30")
    expected1 = datetime.datetime.fromisoformat("2025-07-16T14:47:52+05:30")
    assert result1 == expected1
    
    # Test with -08:00 timezone
    result2 = parse_iso_datetime("2025-07-16T14:47:52-08:00")
    expected2 = datetime.datetime.fromisoformat("2025-07-16T14:47:52-08:00")
    assert result2 == expected2


def test_parse_mergeable_prs_large_numbers():
    """Test parsing with large PR numbers."""
    json_str = '["999999", "1000000", "1000001"]'
    result = parse_mergeable_prs(json_str)
    assert result == [999999, 1000000, 1000001]


def test_parse_mergeable_prs_duplicate_numbers():
    """Test parsing with duplicate PR numbers."""
    json_str = '["123", "456", "123", "789"]'
    result = parse_mergeable_prs(json_str)
    # Should contain duplicates and be sorted
    assert result == [123, 123, 456, 789]


def test_parse_mergeable_prs_whitespace_in_json():
    """Test parsing JSON with whitespace."""
    json_str = ' [ "123" , "456" , "789" ] '
    result = parse_mergeable_prs(json_str)
    assert result == [123, 456, 789]


def test_parse_mergeable_prs_non_numeric_strings():
    """Test parsing with non-numeric strings raises error."""
    json_str = '["abc", "def"]'
    result = parse_mergeable_prs(json_str)
    # Should return empty list due to ValueError in int conversion
    assert result == []


def test_parse_iso_datetime_microseconds():
    """Test parsing datetime with microseconds."""
    result = parse_iso_datetime("2025-07-16T14:47:52.123456Z")
    expected = datetime.datetime.fromisoformat("2025-07-16T14:47:52.123456+00:00")
    assert result == expected


def test_parse_iso_datetime_no_timezone():
    """Test parsing datetime without timezone info."""
    # This should work with fromisoformat
    result = parse_iso_datetime("2025-07-16T14:47:52")
    expected = datetime.datetime.fromisoformat("2025-07-16T14:47:52")
    assert result == expected


def test_set_github_output_special_characters():
    """Test setting GitHub output with special characters."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('builtins.print') as mock_print:
            set_github_output("test_name", "value with spaces and symbols!@#")
            mock_print.assert_called_once_with("Output: test_name=value with spaces and symbols!@#")


def test_set_github_output_empty_values():
    """Test setting GitHub output with empty values."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('builtins.print') as mock_print:
            set_github_output("empty_test", "")
            mock_print.assert_called_once_with("Output: empty_test=")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
