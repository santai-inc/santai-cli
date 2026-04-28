# Security Review: santai-cli v0.1.0

Pre-PyPI publication security audit. Issue: #55

## Summary

| Category | Findings | Fixed |
|----------|----------|-------|
| CRITICAL | 1 | 1 |
| HIGH | 3 | 3 |
| MEDIUM | 4 | 4 |
| LOW | 1 | 1 |

All findings have been remediated in this branch, including both code-level fixes
and infrastructure/CI hardening.

---

## Findings and Fixes Applied

### 1. [CRITICAL] AI chat tools allow arbitrary filesystem access

**File:** `src/santai_cli/core/chat.py:438-442`

`_resolve_path()` performed no boundary checking. An AI model (or prompt injection
via malicious project files) could read, write, or delete files anywhere on the
filesystem through tool calls like `write_file("../../.bashrc", ...)`.

**Fix:** Added `PathTraversalError` exception and boundary validation using
`resolved.relative_to(project_root)`. All seven tool functions (`write_file`,
`read_file`, `list_dir`, `mkdir`, `remove_file`, `remove_dir`, `move`) now catch
and reject paths that escape the project root.

### 2. [HIGH] sdist includes .git and sensitive files

**File:** `pyproject.toml`

No `[tool.hatch.build.targets.sdist]` section existed. Hatchling defaults to
including the entire repo (including `.git/` history) in source distributions.

**Fix:** Added `[tool.hatch.build.targets.sdist] exclude` configuration to
exclude `.git`, `.github`, `.env`, docs, lockfiles, and cache directories.

### 3. [HIGH] `santai push` uploads .env files containing API keys

**File:** `src/santai_cli/commands/push.py`

`_should_include()` only filtered directory names, not file names. `.env` files
(containing `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) would be included in the
zip uploaded to the cloud hub.

**Fix:** `.env` is now excluded by default. Added `--include-env` flag and an
interactive prompt that asks the user whether to include `.env` when one is
detected. The same pattern is applied to `copy` and `merge` commands.

### 4. [HIGH] Zip-slip vulnerability in `santai pull`

**File:** `src/santai_cli/commands/pull.py:104-105`

`zipfile.ZipFile.extractall()` was called without validating member paths. A
malicious zip from a compromised hub could write files outside the destination
directory.

**Fix:** Added member-by-member path validation before extraction. Each member's
resolved path is checked to ensure it stays within `dest_path`. Symlink entries
are also rejected.

### 5. [MEDIUM] .env written without restrictive permissions

**File:** `src/santai_cli/web/app.py:835`

The web settings endpoint wrote `.env` files with default umask permissions
(typically 0o644, world-readable), despite containing API keys.

**Fix:** Added `env_path.chmod(0o600)` after writing to restrict to owner-only.

### 6. [MEDIUM] XSS via unsanitized markdown rendering

**File:** `src/santai_cli/web/templates/index.html`

`marked.parse()` output was injected via `innerHTML` without sanitization in
both the file preview and chat views. Malicious markdown content (e.g., from
pulled projects or AI responses) could execute arbitrary JavaScript.

**Fix:** Added DOMPurify (v3.2.4) as a dependency. Created `safeMarkdown()`
helper for string returns and updated the chat `renderMarkdown(el, content)`
function to sanitize through `DOMPurify.sanitize()`. Also fixed error message
injection to use `textContent` instead of `innerHTML`.

### 7. [MEDIUM] copy/merge commands include .env files

**Files:** `src/santai_cli/commands/copy.py`, `src/santai_cli/commands/merge.py`

`.env` and credential files in the source project would be copied to the
destination without warning.

**Fix:** `.env` is now excluded by default. Added `--include-env` flag and an
interactive prompt that asks the user whether to include `.env` when one is
detected in the source project(s).

### 8. [MEDIUM] Dependencies have no upper-bound constraints

**File:** `pyproject.toml`

All runtime dependencies used `>=` with no upper bound, risking breakage from
future major version bumps when users install from PyPI.

**Fix:** Added upper-bound constraints (e.g., `typer>=0.12.0,<1.0`).

### 9. [LOW] ProviderConfig.api_key visible in repr/tracebacks

**File:** `src/santai_cli/core/config.py:45`

The `api_key` field on the `ProviderConfig` dataclass had `repr=True` (default),
meaning `repr()` or unhandled exception tracebacks would expose the full API key.

**Fix:** Added `field(repr=False)` to the `api_key` field.

---

## Infrastructure & CI Hardening

These items were identified during the audit and addressed in this branch:

### 10. GitHub Actions pinned to commit SHAs

**Files:** `.github/workflows/claude.yml`, `.github/workflows/opencode.yml`

All actions (`actions/checkout`, `anthropics/claude-code-action`,
`anomalyco/opencode/github`) are now pinned to immutable full commit SHAs
with version comments. Previously, `@latest` was used for opencode (floating
tag) and `@v6`/`@v1` for others (mutable tags).

### 11. CI workflows restricted to repo members

**Files:** `.github/workflows/claude.yml`, `.github/workflows/opencode.yml`

Both AI agent workflows (`@claude` and `/oc`) now check
`github.event.comment.author_association` to ensure only `MEMBER`, `OWNER`,
or `COLLABORATOR` users can trigger them. Previously, any commenter could
trigger Claude (which has `contents:write` permission) or OpenCode.

### 12. CODEOWNERS added

**File:** `.github/CODEOWNERS`

Requires review from `@santai-inc/engineering` for changes to:
- `.github/` (CI/CD workflows)
- `pyproject.toml` and `uv.lock` (build config and dependencies)
- `.pre-commit-config.yaml`
- `src/santai_cli/core/config.py` and `commands/auth.py` (security-sensitive)

### 13. Dependabot enabled

**File:** `.github/dependabot.yml`

Configured weekly automated dependency update PRs for both Python packages
(pip ecosystem) and GitHub Actions.

---

## Remaining Items (Manual Configuration Required)

These cannot be addressed via code changes and must be configured in GitHub
repository settings:

| Item | Severity | Action Required |
|------|----------|-----------------|
| Branch protection rules | High | Configure required reviews and status checks on `main` in Settings > Branches |
| CI quality gate | Medium | Add ruff/ty/test workflow that runs on PRs |
| Enable Dependabot alerts | Medium | Enable in Settings > Code security > Dependabot alerts |
| PyPI publish workflow | Medium | Set up Trusted Publishing (OIDC) workflow for tagged releases when ready |
| API key preview exposure | Low | Consider reducing `GET /api/settings` key preview to boolean or last-4-only |
| Web dashboard auth | Low | Document localhost-only binding; consider auth token for non-localhost |
| Hub default URL is HTTP | Low | Consider defaulting to HTTPS or warning when non-localhost hub uses HTTP |

---

## Audit Methodology

- **Dependencies:** `pip-audit` (0 CVEs), `uv lock --check` (in sync), manual review
- **Secrets:** Searched for hardcoded keys, reviewed `.env` loading, checked git/package exclusion
- **Input validation:** Audited all `subprocess`, `eval`/`exec`, Jinja2 templates, file path handling
- **Package build:** Inspected wheel/sdist contents via `uv build`
- **Supply chain:** Reviewed CI workflows, pre-commit hooks, build system configuration
- **Code execution:** Reviewed all dynamic code paths including AI tool dispatch
