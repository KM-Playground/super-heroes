# Merge Queue System Documentation

## Overview

The **Merge Queue System** is a sophisticated GitHub Actions workflow that automates the validation and sequential merging of multiple pull requests with approval workflows, duplicate run prevention, and comprehensive tracking. This system acts as a "merge queue drainer" by processing batches of PRs in a controlled, validated manner.

## Quick Setup

```bash
# Run the setup script to create required labels and check configuration
./scripts/setup-merge-queue.sh
```

## Prerequisites and Setup

### Required Labels

The following labels must exist in your repository:

#### 1. `merge-queue` (Required)
- **Purpose**: Identifies issues that can trigger merge queue workflows
- **Usage**: Applied to issues that contain merge queue requests
- **Creation**: `gh label create merge-queue --description "Issues that can trigger merge queue workflows" --color "0052cc"`

#### 2. `distributed-lock` (Required)
- **Purpose**: Identifies tracking issues used for duplicate run prevention
- **Usage**: Automatically applied to tracking issues created by the system
- **Creation**: `gh label create distributed-lock --description "Tracking issues for preventing duplicate merge queue runs" --color "d73a49"`

#### 3. `automation` (Optional but Recommended)
- **Purpose**: Identifies automated system-generated issues
- **Usage**: Applied to tracking issues and other automated content
- **Creation**: `gh label create automation --description "Automated system-generated content" --color "fbca04"`

### Required Team

#### `merge-approvals` Team
- **Purpose**: Team members who can approve/reject merge queue requests
- **Setup**: Create team in GitHub organization settings
- **Members**: Add users who should have merge queue approval permissions
- **Requirements**: Must have Write or Admin access to the repository

### Required Permissions

The workflow requires the following permissions in the `GITHUB_TOKEN`:
- `contents: read` - For repository access
- `issues: write` - For creating/closing tracking issues and posting comments
- `pull-requests: read` - For reading PR information

### Fine-Grained Personal Access Token

The workflow requires a special token to trigger CI workflows and access team membership:

**Steps to create the token:**
1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **"Generate new token"**
3. Configure with repository-specific access and these permissions:
   - **Administration**: **Read** access (for branch protection rules)
   - **Code**: **Read and Write** access (for branch operations)
   - **Metadata**: **Read** access (for basic repository information)
   - **Pull requests**: **Read and Write** access (for comments and workflow triggers)
   - **Members**: **Read** access (for organization team membership - **organization level permission**)
4. Store as repository secret named `CI_TRIGGER_TOKEN`

**Important Note:** The "Members" permission must be granted at the **organization level**, not just repository level, to access team membership information.

### GitHub Environment

Create a `merge_queue` environment:
1. Go to **repository Settings** → **Environments**
2. Create environment named `merge_queue`
3. Add `merge-approvals` team as required reviewers
4. Set to "Protected branches only"

## Usage

### 1. Create a Merge Queue Request

**Option A: Using GitHub Issue Template**
1. Go to Issues tab → New Issue
2. Select "🚀 Merge Queue Request" template
3. Fill in PR numbers, release PR (optional), and summary

**Option B: Manual Issue Creation**
1. Create issue with `merge-queue` label
2. Include in body:
   ```
   PR Numbers: 123, 124, 125
   Release PR: 126 (optional)
   ```

### 2. Trigger the Merge Queue

Comment `begin-merge` on the issue to start the workflow.

### 3. Approval Process

1. **Individual Team Tagging**: Team members from `merge-approvals` are tagged individually
2. **Approval Methods**:
   - Comment "approved" or react with 👍
   - Comment "rejected" or react with 👎
3. **Authorization**: Only `merge-approvals` team members can approve/reject
4. **Timeout**: 60-minute timeout with 15-minute reminders

## How It Works

### Duplicate Run Prevention (Distributed Locking)

The system uses a distributed locking mechanism to prevent concurrent runs:

1. **Lock Check**: When `begin-merge` is commented, searches for existing tracking issues with:
   - Label: `distributed-lock`
   - Title pattern: `[MERGE QUEUE TRACKING] Issue #<original-issue-number>`

2. **Lock Creation**: If no existing lock found, creates tracking issue with:
   - Title: `[MERGE QUEUE TRACKING] Issue #<original-issue-number> - Auto Merge In Progress`
   - Labels: `distributed-lock`, `automation`
   - Body: Contains original issue reference, PR numbers, and status

3. **Lock Release**: Tracking issue automatically closed when workflow completes

### Workflow Execution Process

The workflow executes through multiple jobs with specific dependencies:

#### Job 1: Team Information Retrieval
- **Uses**: `CI_TRIGGER_TOKEN` with organization-level "Members" permission
- Retrieves `merge-approvals` team member list via GitHub API
- Formats individual member tags for better notifications
- Falls back to team tag if members cannot be accessed
- Exports team information for subsequent jobs

#### Job 2: Initialization with Duplicate Prevention
- **Script**: `initialize_merge_queue.py` (consolidated tracking issue management)
- **Depends on**: Team information from Job 1
- Checks for existing tracking issues using `distributed-lock` label
- Extracts PR information from issue body (PR numbers, release PR, required approvals)
- Creates new tracking issue if none exists
- Exports all data for subsequent jobs
- Aborts if duplicate run detected

#### Job 3: Team Approval Request
- **Uses**: Team information from Job 1
- Tags individual `merge-approvals` team members (or team tag as fallback)
- Waits for approval/rejection (60-minute timeout)
- Sends reminders every 15 minutes using team information

#### Job 4: PR Validation
- Validates PR existence and status
- Checks merge conflicts and approvals
- Categorizes PRs as mergeable/unmergeable

#### Job 5: Sequential PR Merging
- Processes PRs in chronological order (lowest number first)
- For each PR:
  1. Updates branch with latest default branch
  2. Triggers CI with "Ok to test" comment
  3. Waits for CI completion (45-minute timeout)
  4. Performs squash merge with standardized message
  5. Handles branch cleanup based on protection status

#### Job 6: Summary & Cleanup
- **Scripts**: `generate_summary.py` + `close_tracking_issue.py` (independent)
- Posts comprehensive summary to original issue
- Closes original issue automatically
- Closes tracking issue with completion status

## Key Features

### 🔒 Duplicate Run Prevention
- Uses distributed locks with `distributed-lock` labeled tracking issues
- Only one merge queue can run per issue at a time
- Automatic cleanup when workflow completes
- Prevents race conditions and conflicts

### 👥 Individual Team Member Tagging
- Tags each `merge-approvals` team member individually
- No generic team mentions that might be missed
- Clear authorization validation with helpful error messages
- Shows current team members in unauthorized attempt warnings

### 🔄 Robust Sequential Processing
- PRs processed in chronological order (lowest PR number first)
- Comprehensive validation before merging
- Automatic CI triggering and monitoring
- Intelligent branch cleanup based on protection status

### 📊 Transparent Tracking & Reporting
- Tracking issues show active merge queue processes
- Detailed progress updates and final summaries
- Complete audit trail in issue comments
- Immediate notifications for failures

### ⚡ Immediate Feedback System
- PR creators receive instant notifications when issues occur
- No waiting until workflow completion to know about problems
- Actionable guidance provided for each type of failure
- Enables faster problem resolution

### 🏷️ Standardized Merge Messages
- Consistent format: `[Merge Queue] #<PRNumber>-<PRTitle>-<BranchName>`
- Easy to search git history by PR number, keywords, or branch names
- Rich information content for better traceability

### 🛡️ Smart Branch Management
- Uses GitHub API to determine branch protection status
- Automatically preserves protected branches (releases, long-running features)
- Automatically cleans up temporary branches (features, bugfixes)
- No guesswork based on branch naming patterns

## Monitoring

### Active Merge Queues
```bash
# View active merge queue processes
gh issue list --label distributed-lock --state open

# View merge queue history
gh issue list --label merge-queue --state closed

# Check team membership
gh api orgs/YOUR_ORG/teams/merge-approvals/members
```

### Workflow Execution Tracking
- **GitHub Actions**: View workflow runs in repository Actions tab
- **Tracking Issues**: Monitor progress via distributed-lock labeled issues
- **Original Issues**: Check comments for detailed progress updates
- **PR Comments**: Individual failure notifications posted directly to PRs

## Configuration

### Environment Variables

The system uses configurable timeouts and parameters:

```yaml
env:
  APPROVAL_TIMEOUT_MINUTES: "60"      # Approval timeout (default: 60)
  REMINDER_INTERVAL_MINUTES: "15"     # Reminder interval (default: 15)
  CI_TIMEOUT_MINUTES: "45"            # CI completion timeout (default: 45)
  MAX_STARTUP_WAIT: "300"             # CI startup timeout (default: 5 min)
  CHECK_INTERVAL: "30"                # Status check frequency (default: 30 sec)
```

### Timeout Configuration

| Setting | Default | Purpose | Recommended Range |
|---------|---------|---------|-------------------|
| APPROVAL_TIMEOUT_MINUTES | 60 min | Team approval timeout | 30-120 min |
| CI_TIMEOUT_MINUTES | 45 min | CI execution timeout | 30-60 min |
| MAX_STARTUP_WAIT | 5 min | CI startup timeout | 3-10 min |
| REMINDER_INTERVAL_MINUTES | 15 min | Approval reminder frequency | 10-30 min |

### Branch Handling Logic

**Smart Branch Deletion:**
- **Protected Branches**: Automatically preserved (releases, long-running features)
- **Non-Protected Branches**: Automatically deleted after successful merge
- **Detection Method**: Uses GitHub API to check branch protection rules
- **Safe Defaults**: When in doubt, branches are preserved

**Merge Message Format:**
- **Standard PRs**: `[Merge Queue] #<PRNumber>-<PRTitle>-<BranchName>` (squash merge)
- **Release PRs**: `[Merge Queue] #<PRNumber>-<PRTitle>-<BranchName>` (merge commit)

## Troubleshooting

### Common Issues

#### 🔒 "Duplicate run detected"
**Cause**: Another merge queue is already running for this issue
**Solution**: Wait for current process to complete or check tracking issue status
```bash
gh issue list --label distributed-lock --state open
```

#### 👥 "Unauthorized approval"
**Cause**: User is not in `merge-approvals` team
**Solution**: Add user to team in GitHub organization settings
```bash
gh api orgs/YOUR_ORG/teams/merge-approvals/members
```

#### 🏷️ "Label not found"
**Cause**: Required labels don't exist in repository
**Solution**: Run setup script or create labels manually
```bash
./scripts/setup-merge-queue.sh
```

#### 🧪 CI Tests Don't Trigger
**Cause**: `CI_TRIGGER_TOKEN` permissions or `pr-test.yaml` configuration
**Solutions**:
- Verify token permissions and expiration
- Check `pr-test.yaml` workflow exists and triggers on "Ok to test"
- Test manual trigger: `gh pr comment PR_NUMBER --body "Ok to test"`

#### 👥 Team Member Access Issues
**Cause**: `CI_TRIGGER_TOKEN` lacks organization-level "Members" permission
**Symptoms**:
- Workflow fails at "Get team members" step
- Error: "403 Forbidden" or "Resource not accessible by integration"
- Falls back to generic team tag instead of individual member tagging
**Solutions**:
- Ensure `CI_TRIGGER_TOKEN` has **"Read access to members"** at **organization level**
- Verify token is not expired
- Check that `merge-approvals` team exists and has members
- Test manually: `gh api orgs/YOUR_ORG/teams/merge-approvals/members`

#### ⏰ Timeout Issues
**Cause**: CI execution or approval timeouts
**Solutions**:
- Increase timeout values in workflow configuration
- Optimize CI tests for faster execution
- Check GitHub Actions queue status during peak times

### Manual Recovery

If workflow fails partway through:
1. **Identify completed PRs**: Check workflow summary
2. **Update remaining PRs**: Manually update failed PRs with default branch
3. **Re-run with subset**: Trigger workflow with remaining PR numbers
4. **Clean up tracking**: Manually close stuck tracking issues if needed

## Usage Examples

### Example 1: Standard Feature PR Batch
**Scenario**: Merging 5 feature PRs after sprint completion

**Issue Body**:
```
PR Numbers: 1234, 1235, 1236, 1237, 1238
```

**Expected Flow**:
1. Comment `begin-merge` → Creates tracking issue
2. Team members tagged for approval
3. PRs validated and processed in order: #1234 → #1235 → #1236 → #1237 → #1238
4. Each PR: branch update → CI trigger → CI wait → merge
5. Summary posted and issues closed

**Expected Duration**: 15-45 minutes (depending on CI times)

### Example 2: Release + Feature PRs
**Scenario**: Deploying release branch followed by hotfixes

**Issue Body**:
```
PR Numbers: 1240, 1241
Release PR: 1239
```

**Expected Flow**:
1. Release PR #1239 merged first (preserved branch)
2. Feature PRs #1240 and #1241 processed sequentially
3. Summary includes release merge status

**Expected Duration**: 20-50 minutes

## Best Practices

### For Users (PR Authors and Reviewers)

**Before triggering merge queue**:
- ✅ Ensure all PRs are ready for merge and fully reviewed
- ✅ Resolve any merge conflicts beforehand
- ✅ Verify all required approvals are in place
- ✅ Confirm all status checks are passing
- ✅ Use descriptive commit messages (workflow uses squash merge)

**PR Preparation Checklist**:
- [ ] All required reviewers have approved
- [ ] CI tests are passing
- [ ] No merge conflicts with default branch
- [ ] Documentation updated if needed
- [ ] Breaking changes properly communicated

### For Administrators

**Security and Maintenance**:
- 🔐 Regularly review `merge-approvals` team membership
- 🔄 Rotate `CI_TRIGGER_TOKEN` periodically (every 90 days)
- 📊 Monitor workflow execution times and adjust timeouts
- 🛡️ Review branch protection rules alignment
- 📋 Audit workflow usage through GitHub logs

**Performance Optimization**:
- 📈 Monitor CI execution times and optimize slow tests
- 🚀 Consider splitting large PR batches if timeouts occur
- 🔍 Review failed PRs to identify common patterns
- ⚡ Optimize pr-test.yaml workflow for faster execution

## Security Considerations

### Token Security
- 🔒 Treat `CI_TRIGGER_TOKEN` as highly sensitive credential
- 🔄 Rotate every 90 days or per organization policy
- 📊 Monitor usage through GitHub audit logs
- 🚫 Never log or expose token in workflow outputs

### Access Control
- 👥 Limit `merge-approvals` team to essential personnel
- 🔍 Regularly audit team membership (quarterly recommended)
- 📋 Document team member roles and responsibilities
- 🚨 Remove members immediately upon role changes

### Workflow Security
- 🔒 Manual trigger only (no automatic triggers)
- ✅ Requires explicit approval from authorized team members
- 📝 All executions logged and auditable
- 🎯 Limited to protected branches through environment configuration
## Maintenance

### Regular Tasks

**Weekly**:
- Review failed workflow executions
- Monitor immediate notification effectiveness
- Check tracking issue cleanup

**Monthly**:
- Audit `merge-approvals` team membership
- Review notification patterns and response times
- Monitor workflow success rates

**Quarterly**:
- Rotate `CI_TRIGGER_TOKEN`
- Review branch protection rules
- Update timeout configurations based on usage

**Annually**:
- Review and update workflow configuration
- Update notification templates
- Assess system performance and optimization opportunities

### System Health Monitoring

**Performance Metrics**:
- Average CI execution times
- Workflow success rates
- Notification response times
- Common failure patterns

**Cleanup Verification**:
- Tracking issues are properly closed
- Original issues are closed after completion
- No orphaned distributed locks
- Branch cleanup working correctly

## Quick Reference

### Setup Checklist
- [ ] Required labels created (`merge-queue`, `distributed-lock`, `automation`)
- [ ] `merge-approvals` team configured with appropriate members
- [ ] `merge_queue` environment set up with team as reviewers
- [ ] `CI_TRIGGER_TOKEN` created and stored as repository secret
- [ ] `pr-test.yaml` workflow present and functional

### Common Commands
```bash
# View active merge queues
gh issue list --label distributed-lock --state open

# Check team membership
gh api orgs/YOUR_ORG/teams/merge-approvals/members

# Test CI trigger
gh pr comment PR_NUMBER --body "Ok to test"

# Check PR status
gh pr view PR_NUMBER --json mergeable,reviews,statusCheckRollup

# View workflow runs
gh run list --workflow="merge_queue.yaml"
```

### Input Parameters Reference

| Parameter | Required | Format | Example | Description |
|-----------|----------|--------|---------|-------------|
| PR Numbers | ✅ Yes | Comma-separated in issue body | `PR Numbers: 123,124,125` | List of PRs to merge |
| Release PR | ❌ No | Single number in issue body | `Release PR: 999` | Optional release PR to merge first |

## Summary

The **Merge Queue System** provides a comprehensive, enterprise-grade solution for batch merging pull requests with the following key capabilities:

### ✅ Core Features
- **🔒 Distributed Lock System** - Prevents duplicate runs using tracking issues
- **👥 Individual Team Tagging** - Direct member notifications for better visibility
- **🔄 Sequential Processing** - Intelligent PR ordering with comprehensive validation
- **⚡ Immediate Feedback** - Real-time notifications to PR creators
- **🏷️ Standardized Merge Messages** - Consistent, searchable commit messages
- **🛡️ Smart Branch Management** - API-based protection status detection
- **📊 Transparent Tracking** - Complete audit trail and progress monitoring
- **🔐 Security Controls** - Team-based authorization with approval gates

### 🎯 Benefits
- **Prevents Conflicts** - Only one merge queue per issue at a time
- **Improves Developer Experience** - Instant feedback on failures
- **Maintains Code Quality** - Comprehensive validation and CI integration
- **Ensures Compliance** - Complete audit trail and controlled execution
- **Reduces Manual Work** - Automated branch management and cleanup
- **Scales Effectively** - Handles production-scale merge operations

The system is designed for production environments where code quality, developer productivity, and operational reliability are paramount. With recent enhancements including distributed locking and immediate notifications, it provides a superior merge queue experience while maintaining enterprise-grade security and auditability.

---

*For additional support or questions, contact your repository administrators or run the setup script: `./scripts/setup-merge-queue.sh`*
