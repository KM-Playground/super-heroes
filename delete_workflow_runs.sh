#!/bin/bash

# Script to delete all runs for the "Merge Queue Drainer" workflow
# Uses GitHub CLI to interact with the GitHub API

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

# Check if gh CLI is installed and authenticated
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed. Please install it first."
    exit 1
fi

# Check if user is authenticated (check for at least one active account)
AUTH_CHECK=$(gh auth status 2>&1 | grep -c "Active account: true" || true)
if [ "$AUTH_CHECK" -eq 0 ]; then
    print_error "You are not authenticated with GitHub CLI. Please run 'gh auth login' first."
    exit 1
fi

print_info "Starting workflow run deletion process..."

# Get the workflow ID for "Merge Queue Drainer"
print_info "Finding workflow ID for 'Merge Queue Drainer'..."
WORKFLOW_ID=$(gh api repos/:owner/:repo/actions/workflows --jq '.workflows[] | select(.name == "Merge Queue Drainer") | .id')

if [ -z "$WORKFLOW_ID" ]; then
    print_error "Could not find workflow 'Merge Queue Drainer'. Please check the workflow name."
    exit 1
fi

print_success "Found workflow ID: $WORKFLOW_ID"

# Get all workflow runs
print_info "Fetching all workflow runs..."
RUNS=$(gh api repos/:owner/:repo/actions/workflows/$WORKFLOW_ID/runs --paginate --jq '.workflow_runs[].id')

if [ -z "$RUNS" ]; then
    print_warning "No workflow runs found for 'Merge Queue Drainer'."
    exit 0
fi

# Count total runs
TOTAL_RUNS=$(echo "$RUNS" | wc -l | tr -d ' ')
print_info "Found $TOTAL_RUNS workflow runs to delete"

# Confirm deletion
echo
print_warning "This will delete ALL $TOTAL_RUNS runs for the 'Merge Queue Drainer' workflow."
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

for RUN_ID in $RUNS; do
    print_info "Deleting run ID: $RUN_ID"
    
    if gh api repos/:owner/:repo/actions/runs/$RUN_ID -X DELETE &> /dev/null; then
        ((DELETED_COUNT++))
        print_success "Deleted run $RUN_ID ($DELETED_COUNT/$TOTAL_RUNS)"
    else
        ((FAILED_COUNT++))
        print_error "Failed to delete run $RUN_ID"
    fi
    
    # Small delay to avoid rate limiting
    sleep 0.5
done

echo
print_success "Deletion process completed!"
print_info "Successfully deleted: $DELETED_COUNT runs"
if [ $FAILED_COUNT -gt 0 ]; then
    print_warning "Failed to delete: $FAILED_COUNT runs"
fi

print_info "Done!"
