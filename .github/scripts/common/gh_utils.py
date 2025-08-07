#!/usr/bin/env python3
"""
Shared utilities for GitHub CLI operations.

This module provides common functions for executing GitHub CLI commands
across all workflow scripts to avoid code duplication.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CommandResult:
    """Result of a GitHub CLI command execution."""
    success: bool
    stdout: str
    stderr: str


@dataclass
class OperationResult:
    """Result of a GitHub operation (comment, update, etc.)."""
    success: bool
    message: str
    error_details: Optional[str] = None


class GitHubUtils:
    """Utility class for GitHub CLI operations."""

    @staticmethod
    def get_env_var(name: str, default: Optional[str] = None) -> str:
        """Get environment variable with optional default."""
        value = os.environ.get(name)
        if value is None:
            if default is not None:
                return default
            else:
                raise ValueError(f"Required environment variable '{name}' is not set")
        return value

    @staticmethod
    def _run_gh_command(args: List[str], check: bool = True) -> CommandResult:
        """Private method to run a GitHub CLI command and return CommandResult."""
        command = ["gh"] + args
        print(f"🔧 Running command: {' '.join(command)}")
        sys.stdout.flush()  # Force flush to ensure output appears in GitHub Actions logs
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
            return CommandResult(
                success=True,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip()
            )
        except subprocess.CalledProcessError as e:
            return CommandResult(
                success=False,
                stdout=e.stdout.strip() if e.stdout else "",
                stderr=e.stderr.strip() if e.stderr else ""
            )

    @staticmethod
    def get_pr_author(pr_number: str) -> OperationResult:
        """Get PR author using GitHub CLI."""
        result = GitHubUtils._run_gh_command(
            ["pr", "view", pr_number, "--json", "author", "--jq", ".author.login"],
            check=False
        )
        if result.success:
            return OperationResult(success=True, message=result.stdout)
        else:
            error_msg = f"Error getting author for PR #{pr_number}: {result.stderr}"
            print(error_msg)
            return OperationResult(
                success=False,
                message="unknown",
                error_details=error_msg
            )

    @staticmethod
    def comment_on_pr(pr_number: str, message: str) -> OperationResult:
        """Comment on a PR using GitHub CLI."""
        result = GitHubUtils._run_gh_command(
            ["pr", "comment", pr_number, "--body", message],
            check=False
        )
        if result.success:
            success_msg = f"✅ Commented on PR #{pr_number}"
            print(success_msg)
            return OperationResult(success=True, message=success_msg)
        else:
            error_msg = f"❌ Failed to comment on PR #{pr_number}: {result.stderr}"
            print(error_msg)
            return OperationResult(
                success=False,
                message=error_msg,
                error_details=result.stderr
            )

    @staticmethod
    def update_pr_branch(pr_number: str) -> OperationResult:
        """Update PR branch with the default branch."""
        result = GitHubUtils._run_gh_command(
            ["pr", "update-branch", pr_number],
            check=False
        )
        if result.success:
            success_msg = f"✅ Updated PR #{pr_number}"
            print(success_msg)
            return OperationResult(success=True, message=success_msg)
        else:
            error_msg = f"❌ Failed to update PR #{pr_number}: {result.stderr}"
            print(error_msg)
            return OperationResult(
                success=False,
                message=error_msg,
                error_details=result.stderr
            )

    @staticmethod
    def search_issue(label: Optional[str] = None,
                    state: Optional[str] = None,
                    search: Optional[str] = None,
                    json_fields: Optional[str] = None) -> CommandResult:
        """Search for issues using GitHub CLI with optional filters."""
        args = ["issue", "list"]

        if label:
            args.extend(["--label", label])
        if state:
            args.extend(["--state", state])
        if search:
            args.extend(["--search", search])
        if json_fields:
            args.extend(["--json", json_fields])

        return GitHubUtils._run_gh_command(args, check=False)

    @staticmethod
    def add_comment(issue_number: str, comment_body: str) -> OperationResult:
        """Add a comment to an issue using GitHub CLI."""
        result = GitHubUtils._run_gh_command([
            'issue', 'comment', str(issue_number),
            '--body', comment_body
        ], check=False)

        if result.success:
            success_msg = f"✅ Added comment to issue #{issue_number}"
            print(success_msg)
            return OperationResult(success=True, message=success_msg)
        else:
            error_msg = f"❌ Failed to add comment to issue #{issue_number}: {result.stderr}"
            print(error_msg)
            return OperationResult(
                success=False,
                message=error_msg,
                error_details=result.stderr
            )

    @staticmethod
    def create_label(name: str, description: str, color: str) -> OperationResult:
        """Create a label using GitHub CLI."""
        result = GitHubUtils._run_gh_command([
            'label', 'create', name,
            '--description', description,
            '--color', color
        ], check=False)

        if result.success:
            success_msg = f"✅ Created label '{name}'"
            print(success_msg)
            return OperationResult(success=True, message=success_msg)
        else:
            # Check if label already exists
            if "already exists" in result.stderr.lower():
                exists_msg = f"ℹ️ Label '{name}' already exists"
                print(exists_msg)
                return OperationResult(success=True, message=exists_msg)
            else:
                error_msg = f"❌ Failed to create label '{name}': {result.stderr}"
                print(error_msg)
                return OperationResult(
                    success=False,
                    message=error_msg,
                    error_details=result.stderr
                )

    @staticmethod
    def create_issue(title: str, body: str, label: Optional[str] = None) -> CommandResult:
        """Create an issue using GitHub CLI."""
        args = ['issue', 'create', '--title', title, '--body', body]

        if label:
            args.extend(['--label', label])

        return GitHubUtils._run_gh_command(args, check=False)



    @staticmethod
    def get_pr_comments(pr_number: str) -> CommandResult:
        """Get PR comments using GitHub CLI."""
        return GitHubUtils._run_gh_command([
            "pr", "view", str(pr_number),
            "--json", "comments"
        ], check=False)

    @staticmethod
    def get_workflow_run_status(run_id: str) -> CommandResult:
        """Get workflow run status using GitHub CLI."""
        return GitHubUtils._run_gh_command([
            "run", "view", run_id,
            "--json", "status,conclusion,workflowName"
        ], check=False)

    @staticmethod
    def get_pr_branch_name(pr_number: str) -> CommandResult:
        """Get PR branch name using GitHub CLI."""
        return GitHubUtils._run_gh_command([
            "pr", "view", str(pr_number), "--json", "headRefName"
        ], check=False)

    @staticmethod
    def get_pr_details(pr_number: str, json_fields: str) -> CommandResult:
        """Get PR details with specified JSON fields using GitHub CLI."""
        return GitHubUtils._run_gh_command([
            "pr", "view", str(pr_number), "--json", json_fields
        ], check=False)

    @staticmethod
    def merge_pr(pr_number: str, squash: bool = True, delete_branch: bool = False,
                merge_message: Optional[str] = None, admin: bool = False) -> CommandResult:
        """Merge a PR using GitHub CLI."""
        args = ["pr", "merge", str(pr_number)]

        if squash:
            args.append("--squash")
        if admin:
            args.append("--admin")
        if delete_branch:
            args.append("--delete-branch")
        if merge_message:
            args.extend(["--subject", merge_message])

        return GitHubUtils._run_gh_command(args, check=False)

    @staticmethod
    def trigger_ci_comment(pr_number: str, comment_text: str = "Ok to test") -> CommandResult:
        """Post a CI trigger comment on a PR and return the raw result with comment URL."""
        return GitHubUtils._run_gh_command([
            "pr", "comment", str(pr_number),
            "--body", comment_text
        ], check=False)

    @staticmethod
    def get_branch_protection(repository: str, branch: str) -> CommandResult:
        """Get branch protection rules using GitHub API."""
        return GitHubUtils._run_gh_command([
            "api", f"repos/{repository}/branches/{branch}/protection"
        ], check=False)

    @staticmethod
    def is_branch_protected(repository: str, branch: str) -> bool:
        """Check if a branch is protected by querying branch protection rules."""
        result = GitHubUtils.get_branch_protection(repository, branch)

        if not result.success:
            # If we get a 404, the branch is not protected
            # If we get other errors (like 403), we assume it's not protected for safety
            print(f"⚠️ Could not check protection status for branch '{branch}': {result.stderr}")
            return False

        try:
            # Parse the response to check if it's an error or actual protection data
            protection_data = json.loads(result.stdout) if result.stdout else {}

            # Check if this is an error response (GitHub API returns error details in JSON)
            if "message" in protection_data and "status" in protection_data:
                # This is an error response, likely "Branch not protected"
                print(f"✅ Branch '{branch}' protection status: not protected")
                return False

            # If we get here, we have actual protection data, so the branch is protected
            is_protected = bool(protection_data)
            print(f"✅ Branch '{branch}' protection status: {'protected' if is_protected else 'not protected'}")
            return is_protected
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parsing branch protection data for '{branch}': {e}")
            return False

    @staticmethod
    def get_all_comments(issue_number: str) -> CommandResult:
        """
        Get all comments for an issue or PR with consistent field names.

        Note: Uses GitHub CLI which returns camelCase field names (e.g., 'createdAt').
        This is different from the REST API which uses snake_case (e.g., 'created_at').
        """
        return GitHubUtils._run_gh_command([
            "issue", "view", issue_number, "--json", "comments"
        ])

    @staticmethod
    def find_comment_by_id(issue_number: str, comment_id: str) -> dict:
        """Find a specific comment by ID from all comments on an issue/PR."""
        result = GitHubUtils.get_all_comments(issue_number)

        if not result.success:
            return {}

        try:
            import json
            data = json.loads(result.stdout)
            comments = data.get("comments", [])

            # Find the comment with matching ID
            for comment in comments:
                if comment.get("id") == comment_id:
                    return comment

        except (json.JSONDecodeError, KeyError):
            pass

        return {}

    @staticmethod
    def is_team_member(username: str, org: str, team: str) -> bool:
        """Check if a user is a member of the specified team."""
        result = GitHubUtils._run_gh_command([
            "api", f"orgs/{org}/teams/{team}/members/{username}"
        ], check=False)

        return result.success

    @staticmethod
    def get_running_workflows(workflow_name: str) -> CommandResult:
        """Get list of running workflows for a specific workflow file."""
        return GitHubUtils._run_gh_command([
            "run", "list",
            f"--workflow={workflow_name}",
            "--status=in_progress",
            "--json", "status,conclusion"
        ])

    @staticmethod
    def trigger_workflow(workflow_name: str, inputs_json: str) -> CommandResult:
        """Trigger a workflow with the specified inputs."""
        return GitHubUtils._run_gh_command([
            "workflow", "run", workflow_name,
            "--json",
            "--raw-field", f"inputs={inputs_json}"
        ])

    @staticmethod
    def close_issue_with_comment(issue_number: str, comment: str) -> CommandResult:
        """Close an issue with a comment."""
        return GitHubUtils._run_gh_command([
            "issue", "close", issue_number,
            "--comment", comment
        ])
