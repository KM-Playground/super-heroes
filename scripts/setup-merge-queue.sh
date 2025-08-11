#!/bin/bash

# Merge Queue System Setup Script
# This script sets up the required labels and provides guidance for team setup

set -e

echo "🚀 Setting up Merge Queue System"
echo "================================"

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed or not in PATH"
    echo "   Please install it from: https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
echo "🔐 Checking GitHub CLI authentication..."

# Try a simple API call to test authentication
if gh api user > /dev/null 2>&1; then
    echo "✅ GitHub CLI is authenticated"
    # Get the authenticated user for confirmation
    GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
    echo "   Authenticated as: $GITHUB_USER"
else
    echo "❌ Not authenticated with GitHub CLI"
    echo ""
    echo "   Please authenticate with GitHub CLI:"
    echo "   gh auth login"
    echo ""
    echo "   You can check your authentication status with:"
    echo "   gh auth status"
    echo ""
    echo "   If you're already authenticated, try:"
    echo "   gh auth refresh"
    exit 1
fi

echo "✅ GitHub CLI is available and authenticated"
echo ""

# Function to create label if it doesn't exist
create_label_if_not_exists() {
    local name="$1"
    local description="$2"

    if gh label list --json name --jq '.[].name' | grep -q "^${name}$"; then
        echo "✅ Label '${name}' already exists"
    else
        echo "📝 Creating label '${name}'..."
        gh label create "${name}" --description "${description}"
        echo "✅ Created label '${name}'"
    fi
}

echo "📋 Setting up required labels..."
echo "-------------------------------"

# Create required labels
create_label_if_not_exists "merge-queue" "Issues that can trigger merge queue workflows"
create_label_if_not_exists "distributed-lock" "Tracking issues for preventing duplicate merge queue runs"
create_label_if_not_exists "automation" "Automated system-generated content"

echo ""
echo "🏷️  Label setup complete!"
echo ""

# Check for merge-approvals team (this requires org permissions)
echo "👥 Checking team setup..."
echo "-------------------------"

REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
ORG=$(echo "$REPO" | cut -d'/' -f1)

echo "Repository: $REPO"
echo "Organization: $ORG"

# Try to check if merge-approvals team exists
if gh api "orgs/$ORG/teams/merge-approvals" &> /dev/null; then
    echo "✅ Team 'merge-approvals' exists"
    
    # List team members
    echo ""
    echo "Current team members:"
    gh api "orgs/$ORG/teams/merge-approvals/members" --jq '.[].login' | sed 's/^/  - /'
else
    echo "⚠️  Team 'merge-approvals' does not exist or you don't have permission to view it"
    echo ""
    echo "📝 Manual setup required:"
    echo "   1. Go to: https://github.com/orgs/$ORG/teams"
    echo "   2. Create a new team named 'merge-approvals'"
    echo "   3. Add team members who should be able to approve merge queue requests"
    echo "   4. Set team visibility as needed for your organization"
fi

echo ""
echo "🔧 Workflow permissions..."
echo "-------------------------"

echo "The merge queue workflow requires these permissions:"
echo "  - contents: read"
echo "  - issues: write" 
echo "  - pull-requests: read"
echo ""
echo "These are already configured in the workflow file."

echo ""
echo "📚 Documentation..."
echo "------------------"

echo "Complete documentation is available at:"
echo "  - docs/merge-queue-system.md"
echo ""
echo "Key files to review:"
echo "  - .github/workflows/merge_queue.yaml (main workflow)"
echo "  - .github/scripts/merge_queue/ (workflow scripts)"

echo ""
echo "🎉 Setup Complete!"
echo "=================="

echo ""
echo "✅ Labels created successfully"
if gh api "orgs/$ORG/teams/merge-approvals" &> /dev/null; then
    echo "✅ Team 'merge-approvals' is configured"
else
    echo "⚠️  Team 'merge-approvals' needs manual setup"
fi
echo "✅ Workflow permissions are configured"
echo "✅ Documentation is available"

echo ""
echo "🚀 Ready to use!"
echo ""
echo "To test the merge queue:"
echo "  1. Create an issue with the 'merge-queue' label"
echo "  2. Add PR numbers in the issue body: 'PR Numbers: 123, 124'"
echo "  3. Comment 'begin-merge' on the issue"
echo ""
echo "The system will create a tracking issue and request approval from the merge-approvals team."

echo ""
echo "🔍 Monitor active merge queues:"
echo "   gh issue list --label distributed-lock --state open"
echo ""
echo "🧹 Clean up workflow runs (optional):"
echo "   ./delete_workflow_runs.sh --help           # See cleanup options"
echo "   ./delete_workflow_runs.sh \"Merge Queue\"    # Delete only merge queue runs"
echo "   ./delete_workflow_runs.sh                  # Delete ALL workflow runs"
