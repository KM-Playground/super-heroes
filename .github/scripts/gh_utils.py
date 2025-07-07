#!/usr/bin/env python3
"""
Shared utilities for GitHub CLI operations.

This module provides common functions for executing GitHub CLI commands
across all workflow scripts to avoid code duplication.
"""

import subprocess
from typing import List, Tuple


def get_env_var(name: str, default: str = "") -> str:
    """Get environment variable with optional default."""
    import os
    return os.environ.get(name, default)


def run_gh_command(args: List[str], check: bool = True) -> Tuple[bool, str, str]:
    """Run a GitHub CLI command and return success, stdout, stderr."""
    command = ["gh"] + args
    print(f"🔧 Running command: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else ""


def get_pr_author(pr_number: str) -> str:
    """Get PR author using GitHub CLI."""
    success, stdout, stderr = run_gh_command(
        ["pr", "view", pr_number, "--json", "author", "--jq", ".author.login"], 
        check=False
    )
    if success:
        return stdout
    else:
        print(f"Error getting author for PR #{pr_number}: {stderr}")
        return "unknown"


def comment_on_pr(pr_number: str, message: str) -> bool:
    """Comment on a PR using GitHub CLI."""
    success, stdout, stderr = run_gh_command(
        ["pr", "comment", pr_number, "--body", message], 
        check=False
    )
    if success:
        print(f"✅ Commented on PR #{pr_number}")
        return True
    else:
        print(f"❌ Failed to comment on PR #{pr_number}: {stderr}")
        return False


def update_pr_branch(pr_number: str) -> bool:
    """Update PR branch with the default branch."""
    success, stdout, stderr = run_gh_command(
        ["pr", "update-branch", pr_number], 
        check=False
    )
    if success:
        print(f"✅ Updated PR #{pr_number}")
        return True
    else:
        print(f"❌ Failed to update PR #{pr_number}: {stderr}")
        return False
