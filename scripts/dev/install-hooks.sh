#!/usr/bin/env bash
# Install the Git hooks. Run once after cloning: make hooks
#
#   pre-commit  gitleaks + account-ID check on what's staged (SPEC-001-R6)
#   commit-msg  the commit convention (scripts/dev/check_commits.py, SPEC-001-R5)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK="$ROOT/.git/hooks/pre-commit"
MSG_HOOK="$ROOT/.git/hooks/commit-msg"

[[ -d "$ROOT/.git" ]] || { echo "not a git repository — run 'git init' first"; exit 1; }

cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Thalam pre-commit — block secrets before they enter history. The repository is public, so a
# secret committed today and removed tomorrow is still published. This is the cheap moment.

set -euo pipefail

if command -v gitleaks >/dev/null 2>&1; then
  # `git --staged` is the working scan in gitleaks v8.20+; the old `protect` is a silent no-op.
  if ! gitleaks git --staged --redact --config .gitleaks.toml --no-banner; then
    echo ""
    echo "  Commit blocked: a possible secret or real address is staged."
    echo "  A genuine false positive goes in .gitleaks.toml's allowlist with a comment saying why."
    echo "  Do not use --no-verify."
    echo ""
    exit 1
  fi
else
  echo "  WARNING: gitleaks not installed — commit NOT scanned (CI still scans)."
fi

# Belt and braces: a real 12-digit account ID that slipped past the rules. The boundaries
# exclude hex letters, so a digit run inside a sha256 (uv.lock) doesn't count.
if git diff --cached -U0 | grep -nE '^\+(.*[^0-9a-fA-F])?[0-9]{12}([^0-9a-fA-F]|$)' \
     | grep -vE '000000000000' >/dev/null 2>&1; then
  echo ""
  echo "  A 12-digit number is being committed. If that is an AWS account ID,"
  echo "  replace it with a variable or the 000000000000 placeholder."
  echo ""
  read -p "  Continue anyway? [y/N] " ok < /dev/tty
  [[ "$ok" == "y" ]] || exit 1
fi
EOF
chmod +x "$HOOK"
echo "installed: .git/hooks/pre-commit"

cat > "$MSG_HOOK" <<'EOF'
#!/usr/bin/env bash
# Thalam commit-msg — the commit convention, checked before the commit exists (SPEC-001-R5).

set -euo pipefail

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "  WARNING: no python found — commit message NOT checked (CI still checks it)."
  exit 0
fi
BRANCH="$(git symbolic-ref --short -q HEAD || true)"
exec "$PY" scripts/dev/check_commits.py --file "$1" --branch "$BRANCH"
EOF
chmod +x "$MSG_HOOK"
echo "installed: .git/hooks/commit-msg"
