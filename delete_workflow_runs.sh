#!/bin/bash

# Enhanced Script to delete ALL workflow runs across ALL workflows
# Uses GitHub CLI to interact with the GitHub API
#
# Usage:
#   ./delete_workflow_runs.sh                    # Delete all runs for all workflows
#   ./delete_workflow_runs.sh "Merge Queue"     # Delete runs for specific workflow (partial name match)
#   ./delete_workflow_runs.sh --help            # Show help

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show help
show_help() {
    echo "Enhanced Workflow Run Deletion Script"
    echo "====================================="
    echo ""
    echo "Usage:"
    echo "  $0                           # Delete ALL runs for ALL workflows"
    echo "  $0 \"workflow-name\"           # Delete runs for specific workflow (partial name match)"
    echo "  $0 --help                   # Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Delete everything"
    echo "  $0 \"Merge Queue\"             # Delete only Merge Queue workflow runs"
    echo "  $0 \"CI\"                      # Delete runs for workflows containing 'CI'"
    echo ""
    echo "Options:"
    echo "  --help, -h                  Show this help message"
    echo ""
    echo "Note: This script will ask for confirmation before deleting anything."
}

# Handle command line arguments
WORKFLOW_FILTER=""
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
elif [ -n "$1" ]; then
    WORKFLOW_FILTER="$1"
    print_info "Filtering workflows containing: '$WORKFLOW_FILTER'"
else
    print_info "Will delete runs for ALL workflows"
fi

# Check if gh CLI is installed and authenticated
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed. Please install it first."
    exit 1
fi

# Check if user is authenticated using a more reliable method
print_info "Checking GitHub CLI authentication..."
if ! gh api user > /dev/null 2>&1; then
    print_error "You are not authenticated with GitHub CLI."
    print_error "Please run: gh auth login"
    exit 1
fi

GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
print_success "Authenticated as: $GITHUB_USER"

print_info "Starting workflow run deletion process..."

# Get all workflows
print_info "Fetching all workflows..."
if [ -n "$WORKFLOW_FILTER" ]; then
    WORKFLOWS=$(gh api repos/:owner/:repo/actions/workflows --jq ".workflows[] | select(.name | contains(\"$WORKFLOW_FILTER\")) | {id: .id, name: .name}")
    print_info "Found workflows matching '$WORKFLOW_FILTER':"
else
    WORKFLOWS=$(gh api repos/:owner/:repo/actions/workflows --jq '.workflows[] | {id: .id, name: .name}')
    print_info "Found all workflows:"
fi

if [ -z "$WORKFLOWS" ]; then
    if [ -n "$WORKFLOW_FILTER" ]; then
        print_warning "No workflows found matching '$WORKFLOW_FILTER'."
    else
        print_warning "No workflows found in this repository."
    fi
    exit 0
fi

# Display workflows that will be processed
echo "$WORKFLOWS" | jq -r '"  - " + .name + " (ID: " + (.id | tostring) + ")"'
echo

# Get all workflow runs across all matching workflows
print_info "Fetching all workflow runs..."
ALL_RUNS=""
WORKFLOW_COUNT=0

while IFS= read -r workflow; do
    if [ -n "$workflow" ]; then
        WORKFLOW_ID=$(echo "$workflow" | jq -r '.id')
        WORKFLOW_NAME=$(echo "$workflow" | jq -r '.name')

        print_info "Fetching runs for: $WORKFLOW_NAME"
        RUNS=$(gh api repos/:owner/:repo/actions/workflows/$WORKFLOW_ID/runs --paginate --jq '.workflow_runs[].id' 2>/dev/null || echo "")

        if [ -n "$RUNS" ]; then
            if [ -n "$ALL_RUNS" ]; then
                ALL_RUNS="$ALL_RUNS"$'\n'"$RUNS"
            else
                ALL_RUNS="$RUNS"
            fi
            RUN_COUNT=$(echo "$RUNS" | wc -l | tr -d ' ')
            print_success "Found $RUN_COUNT runs for $WORKFLOW_NAME"
        else
            print_info "No runs found for $WORKFLOW_NAME"
        fi

        ((WORKFLOW_COUNT++))
    fi
done <<< "$WORKFLOWS"

if [ -z "$ALL_RUNS" ]; then
    print_warning "No workflow runs found."
    exit 0
fi

# Count total runs
TOTAL_RUNS=$(echo "$ALL_RUNS" | wc -l | tr -d ' ')
print_info "Found $TOTAL_RUNS total workflow runs to delete across $WORKFLOW_COUNT workflows"

# Confirm deletion
echo
if [ -n "$WORKFLOW_FILTER" ]; then
    print_warning "This will delete ALL $TOTAL_RUNS runs for workflows matching '$WORKFLOW_FILTER'."
else
    print_warning "This will delete ALL $TOTAL_RUNS runs for ALL workflows in this repository."
fi
print_warning "This action cannot be undone!"
echo
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Operation cancelled."
    exit 0
fi

# Delete each run
print_info "Starting deletion process..."
DELETED_COUNT=0
FAILED_COUNT=0

for RUN_ID in $ALL_RUNS; do
    if [ -n "$RUN_ID" ]; then
        print_info "Deleting run ID: $RUN_ID"

        if gh api repos/:owner/:repo/actions/runs/$RUN_ID -X DELETE &> /dev/null; then
            ((DELETED_COUNT++))
            print_success "Deleted run $RUN_ID ($DELETED_COUNT/$TOTAL_RUNS)"
        else
            ((FAILED_COUNT++))
            print_error "Failed to delete run $RUN_ID"
        fi

        # Small delay to avoid rate limiting
        sleep 0.3
    fi
done

echo
print_success "Deletion process completed!"
print_info "Successfully deleted: $DELETED_COUNT runs"
if [ $FAILED_COUNT -gt 0 ]; then
    print_warning "Failed to delete: $FAILED_COUNT runs"
fi

if [ -n "$WORKFLOW_FILTER" ]; then
    print_info "Processed workflows matching: '$WORKFLOW_FILTER'"
else
    print_info "Processed all workflows in the repository"
fi

print_success "Done! Repository workflow history cleaned up."
