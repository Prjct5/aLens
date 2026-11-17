#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-Prjct5/aLens}"
REVIEWERS="${PRODUCTION_REVIEWERS:-}"

command -v gh >/dev/null || { echo "install GitHub CLI: https://cli.github.com"; exit 1; }
gh auth status >/dev/null

echo "== repository settings"
gh api -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true -F has_wiki=false >/dev/null

echo "== security"
gh api -X PATCH "repos/$REPO" \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled' >/dev/null || \
  echo "WARN: could not enable secret scanning via API; enable it in Settings > Security"
gh api -X PUT "repos/$REPO/vulnerability-alerts" >/dev/null || echo "WARN: dependabot alerts"
gh api -X PUT "repos/$REPO/automated-security-fixes" >/dev/null || echo "WARN: dependabot updates"

echo "== actions: approval for outside collaborators"
gh api -X PUT "repos/$REPO/actions/permissions/fork-pr-contributor-approval" \
  -f approval_policy=all_external_contributors >/dev/null || \
  echo "WARN: set 'Require approval for all outside collaborators' in Settings > Actions > General"

echo "== labels"
create_label() {
  gh api -X POST "repos/$REPO/labels" -f name="$1" -f color="$2" -f description="$3" >/dev/null 2>&1 \
    || gh api -X PATCH "repos/$REPO/labels/$1" -f color="$2" -f description="$3" >/dev/null
}
for m in m1 m2 m3 m4 m5; do create_label "$m" "1d76db" "Owned by $m"; done
create_label contract-change "d93f0b" "Changes a shared interface"
create_label blocked "b60205" "Waiting on something"
create_label bug "ee0701" "Something is broken"
create_label data-quality "fbca04" "Data quality issue"
create_label pipeline-failure "5319e7" "Opened by nightly health"

echo "== milestones"
for w in 1 2 3 4 5 6 7 8; do
  gh api -X POST "repos/$REPO/milestones" -f title="week-$w" >/dev/null 2>&1 || true
done

echo "== environments"
gh api -X PUT "repos/$REPO/environments/staging" >/dev/null
if [ -n "$REVIEWERS" ]; then
  ids=()
  for login in ${REVIEWERS//,/ }; do
    ids+=("$(gh api "users/$login" --jq .id)")
  done
  body=$(printf '{"reviewers":[%s]}' "$(for i in "${ids[@]}"; do printf '{"type":"User","id":%s},' "$i"; done | sed 's/,$//')")
  echo "$body" | gh api -X PUT "repos/$REPO/environments/production" --input - >/dev/null
else
  gh api -X PUT "repos/$REPO/environments/production" >/dev/null
  echo "WARN: production has no required reviewers; rerun with PRODUCTION_REVIEWERS=login1,login2"
fi

echo "== branch protection on main"
cat <<JSON | gh api -X PUT "repos/$REPO/branches/main/protection" --input - >/dev/null
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["lint", "unit", "contracts", "e2e", "docker"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

echo "done"
