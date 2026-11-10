---
name: ship-safe
description: Audit a repository before it becomes public or ships. Use when the user asks "can I publish this", "is this safe to make public", "secret scan", "license audit", "release check", or before flipping a repo from private to public. Covers secrets in the working tree and in Git history, personal data, third-party licenses, and a clean release checklist.
---

# Ship safe

Publishing is not a file operation, it is a disclosure. A secret deleted today
is still in yesterday's commits, and a public repo keeps reachable objects.

## 1. Inventory

```sh
git status --short
git log --oneline
git ls-files | wc -l
git remote -v
```

List tracked files, total size, and the branches. Note anything larger than a few
MB (assets, models, audio) — it may carry a license.

## 2. Secrets in the working tree

Scan filenames first, then contents. Never print a matching value into the chat;
mask it.

```sh
git ls-files | grep -Ei '(\.env|\.pem|\.key|id_rsa|auth\.json|service\.json|credentials|secret)'
git grep -n -I -E '(api[_-]?key|access[_-]?token|client[_-]?secret|password|bearer)[[:space:]]*[:=]'
git grep -n -I -E '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|msy_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-)'
git grep -n -I -E 'BEGIN [A-Z ]*PRIVATE KEY'
```

Report `file:line` and the type, never the value.

## 3. Secrets in history

This is the step people skip.

```sh
git log --all --diff-filter=D --name-only --pretty=format:'--- %h %s'
git rev-list --all | while read c; do git grep -I -l -E '(sk-|ghp_|github_pat_|msy_|BEGIN .*PRIVATE KEY)' "$c" -- 2>/dev/null; done
```

If a secret was ever committed, assume it is compromised: rotate it, then decide
between a fresh history and a rewrite (`git filter-repo`). Deleting the file and
flipping visibility is **not** enough.

## 4. Personal data

```sh
git grep -n -I -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
git grep -n -I -E 'C:\\\\Users\\\\|/home/[a-z]|192\.168\.|100\.[0-9]+\.[0-9]+\.[0-9]+|\.ts\.net'
git grep -n -I -E '(client|kunde|internal|confidential)' -i
```

Check memory exports, notes, vocabulary files, and test fixtures. Client names
and project paths are not secrets, but they are not for the public either.

## 5. Licenses

- Is there a `LICENSE`? If not, the code is "all rights reserved" by default.
- Which files came from elsewhere? Skills, assets, music, fonts, sample code.
- For each: source URL, license, and whether redistribution is allowed.
- Assets with unclear licenses are excluded, not guessed.
- Add `THIRD_PARTY.md`; keep attribution files next to the asset.

## 6. History decision

| Situation | Action |
| --- | --- |
| Secrets or private data ever committed | Fresh repo or `git filter-repo`, rotate first |
| Only clean commits, but internal notes in tree | Remove, commit, then publish |
| Never published, no secrets in history | Private first, review, then public |

Prefer a fresh repository over rewriting when the public product is a subset of a
private working repo.

## 7. Release artifacts

- `LICENSE` with the intended terms.
- `THIRD_PARTY.md` for bundled third-party work.
- `README` that states what is included and what is deliberately not.
- `.gitignore` for secrets, memory, virtualenvs, caches, build output.
- `.gitattributes` for line endings on cross-platform scripts.
- No `memory/export.json`, no session database, no service config.

## 8. Publish

```sh
gh repo create <owner>/<repo> --private --source . --remote origin --push
# review the rendered page and the raw files
gh repo edit <owner>/<repo> --visibility public --accept-visibility-change-consequences
```

Verify after publishing:

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://github.com/<owner>/<repo>
curl -s -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/<owner>/<repo>/main/<asset>
```

## Report format

| Area | Result | Blocker? |
| --- | --- | --- |
| Secrets (tree) | none / found | yes |
| Secrets (history) | none / found | yes |
| Personal data | none / list | usually |
| Licenses | complete / gaps | yes for unclear assets |
| History | fresh / rewrite needed | yes |
| Release files | complete / missing | no |

End with the single decision: **safe to publish**, **publish after fixes**, or
**do not publish**.
