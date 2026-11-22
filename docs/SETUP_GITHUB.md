# GitHub setup (repository owner, M5)

## 1. First push (before branch protection)

```bash
unzip aLens-bootstrap.zip && cd aLens
git init -b main
git add .
git commit -m "chore: bootstrap repository skeleton"
git remote add origin https://github.com/Prjct5/aLens.git
git push -u origin main
```

Enable two-factor authentication on the `Prjct5` account.

## 2. Invite members

Settings > Collaborators > add Merna Mohamed (M1), Mohamed Shreif (M2), Mohamed Gamal (M3),
Mahmoud Nadeem (M4) with the Write role. Record usernames in `docs/TEAM.md`.

## 3. Fill CODEOWNERS (once everyone has accepted)

```bash
python scripts/fill_codeowners.py --m1 <user> --m2 <user> --m3 <user> --m4 <user> --m5 Prjct5
git add .github/CODEOWNERS docs/TEAM.md
git commit -m "chore: set CODEOWNERS and team usernames"
git push
```

## 4. Apply settings and protection

Check that the first CI run on `main` finished (checks `lint unit contracts e2e docker` must exist).

```bash
gh auth login
PRODUCTION_REVIEWERS=<user1>,<user2> ./scripts/apply_github_settings.sh
```

This applies: squash-merge only, auto-delete branches, secret scanning and push protection,
Dependabot, outside-collaborator approval, labels, milestones week-1..week-8, environments
`staging` and `production`, and protection on `main` (PR + 1 code-owner approval, required
checks, linear history, no force-push, no bypass for admins).

From now on every change, including yours, goes through a pull request.

## 5. Optional, when a server exists

Install a self-hosted runner as a service on the staging machine, create `/opt/autolens/.env`
and set the runner variable `AUTOLENS_ENV_FILE=/opt/autolens/.env`. Then set repository
variables (Settings > Secrets and variables > Actions > Variables):

- `STAGING_ENABLED=true` (enables staging deploy and nightly health)
- `PRODUCTION_ENABLED=true` (enables deploy on version tags)
- `MLFLOW_TRACKING_URI` (used by the model-gate workflow)

## 6. Backup

```bash
git clone --mirror https://github.com/Prjct5/aLens.git aLens-mirror.git
cd aLens-mirror.git && git remote update
```

Repeat weekly.

## Manual settings the script cannot guarantee

Verify in the GitHub UI: Settings > Branches (rule on `main`), Settings > Code security
(secret scanning, push protection), Settings > Actions > General (approval for all outside
collaborators).

## Adding the M1 integration to an existing repository

```bash
cd aLens                                  # your clone
git checkout -b feat/m5-m1-integration
# copy the contents of aLens-m1-integration.zip over the clone, then restore the files you edited by hand:
git checkout -- .github/CODEOWNERS docs/TEAM.md
git add -A && git commit -m "feat: integrate M1 scrapers, linkage and typed staging tables"
git push -u origin feat/m5-m1-integration
```

Open a pull request. With protection enabled it needs green CI and one code-owner approval
from a teammate (M1 or M2 can approve). Check `git status` shows no `data`, `raw`, `outputs`
or `.env` before committing.
