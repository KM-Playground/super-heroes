/**
 * Generate PR merge summary report
 * This script creates a detailed summary of the PR merge process results
 */

function generateSummary(data) {
  const {
    spoc,
    totalRequested,
    merged = [],
    unmergeable = [],
    failedUpdate = [],
    failedCI = [],
    timeout = [],
    failedMerge = []
  } = data;

  const totalMerged = merged.length;
  const totalFailed = unmergeable.length + failedUpdate.length + failedCI.length + timeout.length + failedMerge.length;
  const date = new Date().toISOString().split('T')[0];

  let summary = `# PR Merge Summary - ${date}

## Overview
- **Total PRs Requested**: ${totalRequested}
- **Successfully Merged**: ${totalMerged}
- **Failed to Merge**: ${totalFailed}

## Successfully Merged PRs ✅
`;

  if (merged.length > 0) {
    summary += merged.map(pr => `- PR #${pr}`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

## Failed PRs by Category ❌

### Initial Validation Failures
`;
  if (unmergeable.length > 0) {
    summary += unmergeable.map(pr => `- PR #${pr} (insufficient approvals, failing checks, or not targeting master)`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

### Update with Master Failed
`;
  if (failedUpdate.length > 0) {
    summary += failedUpdate.map(pr => `- PR #${pr} (could not update branch with master)`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

### CI Checks Failed
`;
  if (failedCI.length > 0) {
    summary += failedCI.map(pr => `- PR #${pr} (CI checks failed after update)`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

### CI Timeout
`;
  if (timeout.length > 0) {
    summary += timeout.map(pr => `- PR #${pr} (CI did not complete within 45 minutes)`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

### Merge Operation Failed
`;
  if (failedMerge.length > 0) {
    summary += failedMerge.map(pr => `- PR #${pr} (merge command failed)`).join('\n');
  } else {
    summary += '- None';
  }

  summary += `

---
*Workflow executed by @${spoc}*`;

  return {
    title: `PR Merge Summary - ${date}`,
    body: summary
  };
}

// Function to get PR author
async function getPRAuthor(octokit, owner, repo, prNumber) {
  try {
    const pr = await octokit.rest.pulls.get({
      owner,
      repo,
      pull_number: parseInt(prNumber)
    });
    return pr.data.user.login;
  } catch (error) {
    console.error(`Failed to get author for PR #${prNumber}:`, error.message);
    return null;
  }
}

// Function to comment on failed PRs
async function commentOnFailedPRs(octokit, owner, repo, spoc, failureData) {
  const failureMessages = {
    unmergeable: "❌ This PR could not be merged due to one or more of the following:\n\n- Less than 2 approvals\n- Failing or missing status checks\n- Not up-to-date with `master`\n- Not targeting `master`\n\nPlease address these issues to include it in the next merge cycle.",
    failedUpdate: "❌ This PR could not be updated with the latest `master` branch. There may be merge conflicts that need to be resolved manually.\n\nPlease resolve any conflicts and ensure the PR can be cleanly updated with `master`.",
    failedCI: "❌ This PR's CI checks failed after being updated with `master`. Please review the failing checks and fix any issues.\n\nThe PR has been updated with the latest `master` - please check if this caused any new test failures.",
    timeout: "⏰ This PR's CI checks did not complete within the 45-minute timeout period after being updated with `master`.\n\nThe PR has been updated with the latest `master` - please check the CI status and re-run if needed.",
    failedMerge: "❌ This PR failed to merge despite passing all checks. This may be due to a last-minute conflict or GitHub API issue.\n\nThe PR has been updated with the latest `master` - please try merging manually or contact the repository administrators."
  };

  for (const [category, prs] of Object.entries(failureData)) {
    if (prs.length === 0) continue;

    for (const prNumber of prs) {
      try {
        const author = await getPRAuthor(octokit, owner, repo, prNumber);
        const authorMention = author ? `@${author}` : 'PR author';

        const message = `${authorMention} @${spoc}, ${failureMessages[category]}`;

        await octokit.rest.issues.createComment({
          owner,
          repo,
          issue_number: parseInt(prNumber),
          body: message
        });

        console.log(`Commented on PR #${prNumber} for ${category} failure`);
      } catch (error) {
        console.error(`Failed to comment on PR #${prNumber}:`, error.message);
      }
    }
  }
}

// Function to update PRs with master (for CI failures and timeouts)
async function updatePRsWithMaster(octokit, owner, repo, prsToUpdate) {
  for (const prNumber of prsToUpdate) {
    try {
      await octokit.rest.pulls.updateBranch({
        owner,
        repo,
        pull_number: parseInt(prNumber)
      });
      console.log(`Updated PR #${prNumber} with master`);
    } catch (error) {
      console.error(`Failed to update PR #${prNumber} with master:`, error.message);
    }
  }
}

// Main execution for GitHub Actions
async function main() {
  const { github, context } = require('@actions/github');
  const core = require('@actions/core');

  try {
    // Get inputs from environment variables
    const totalRequestedRaw = process.env.TOTAL_REQUESTED_RAW || '';
    const totalRequested = totalRequestedRaw.split(',').filter(pr => pr.trim()).length;

    const spoc = process.env.SPOC;

    // Parse comma-separated strings into arrays
    const parseCommaSeparated = (str) => str ? str.split(',').filter(item => item.trim()) : [];

    const merged = parseCommaSeparated(process.env.MERGED);
    const unmergeable = JSON.parse(process.env.UNMERGEABLE || '[]'); // This one is still JSON from validate-prs
    const failedUpdate = parseCommaSeparated(process.env.FAILED_UPDATE);
    const failedCI = parseCommaSeparated(process.env.FAILED_CI);
    const timeout = parseCommaSeparated(process.env.TIMEOUT);
    const failedMerge = parseCommaSeparated(process.env.FAILED_MERGE);

    const token = process.env.GITHUB_TOKEN;
    const octokit = github.getOctokit(token);
    const { owner, repo } = context.repo;

    // Comment on all failed PRs with specific reasons
    const failureData = {
      unmergeable,
      failedUpdate,
      failedCI,
      timeout,
      failedMerge
    };

    await commentOnFailedPRs(octokit, owner, repo, spoc, failureData);

    // Update PRs with master for CI failures and timeouts
    const prsToUpdate = [...failedCI, ...timeout, ...failedMerge];
    if (prsToUpdate.length > 0) {
      console.log(`Updating ${prsToUpdate.length} PRs with master: ${prsToUpdate.join(', ')}`);
      await updatePRsWithMaster(octokit, owner, repo, prsToUpdate);
    }

    // Generate and log summary for workflow logs
    const data = {
      spoc,
      totalRequested,
      merged,
      unmergeable,
      failedUpdate,
      failedCI,
      timeout,
      failedMerge
    };

    const summary = generateSummary(data);
    console.log('='.repeat(50));
    console.log(summary.body);
    console.log('='.repeat(50));

    console.log('PR notifications and updates completed successfully');
  } catch (error) {
    core.setFailed(`Failed to process PR notifications: ${error.message}`);
  }
}

// Export for testing or direct usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { generateSummary };
}

// Run if called directly
if (require.main === module) {
  main();
}
