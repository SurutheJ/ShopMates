# Git workflow

## Branches

- `main`: always working. Nothing is committed to it directly. It only receives merges from reviewed pull requests.
- `feature/<short-description>`: one branch per feature or task, branched from the latest `main`.
- `fix/<short-description>`: bug fixes, same pattern.

## Workflow

1. `git checkout main && git pull origin main`
2. `git checkout -b feature/your-feature`
3. Commit small, with clear messages.
4. `git push -u origin feature/your-feature` and open a pull request into `main`.
5. A teammate reviews it before merge. A review must exist on the PR.
6. Merge, then delete the feature branch.

## Commit messages

A short imperative summary (about 50 characters), then an optional blank line and detail about *why*.

```
Add redemption validation for caps and dates

Reject confirmations when the deal is not active, the date is outside
the window, the cap is reached, or the code was already used.
```

## Never commit

- `.env` or any file with keys, tokens, or passwords
- `db.sqlite3`
- Model weights or large binaries
- Editor folders such as `.idea/`

Stage files by name, not with `git add .`, and check `git status` before committing.

## Before opening a PR

- The app runs and tests pass
- No secrets in the diff (search it for `KEY`, `SECRET`, `TOKEN`)
- Docs updated if behavior changed
