#!/usr/bin/env bash
# Install the Git hooks. Run once after cloning: make hooks (or bash scripts/dev/install-hooks.sh)
#
#   pre-commit  gitleaks + account-ID check on what's staged (SPEC-001-R6)
#   commit-msg  the commit convention (scripts/dev/check_commits.py, SPEC-001-R5)
#
# Hooks go where git looks for them: `git rev-parse --git-path hooks` honours worktrees and
# core.hooksPath. A hook this script did not write is kept as <name>.bak, never overwritten.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 \
  || { echo "not a git repository — run 'git init' first"; exit 1; }
HOOKS="$(cd "$ROOT" && git rev-parse --path-format=absolute --git-path hooks)"
mkdir -p "$HOOKS"
MARK="# thalam-managed hook"

install_hook() {  # $1 = hook path; the hook's text arrives on stdin
  if [[ -f "$1" ]] && ! grep -qF "$MARK" "$1"; then
    mv "$1" "$1.bak"
    echo "kept the previous hook as $1.bak"
  fi
  cat > "$1"
  chmod +x "$1"
  echo "installed: $1"
}

install_hook "$HOOKS/pre-commit" <<'EOF'
#!/usr/bin/env bash
# thalam-managed hook
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
# exclude hex letters, so a digit run inside a sha256 (uv.lock) doesn't count. The placeholder
# is removed first, so a real ID on the same line as 000000000000 is still seen. grep reads all
# of its input (no -q), so pipefail cannot turn a match into a SIGPIPE failure.
if git diff --cached --no-color --no-ext-diff -U0 | sed 's/000000000000//g' \
     | grep -E '^\+(.*[^0-9a-fA-F])?[0-9]{12}([^0-9a-fA-F]|$)' >/dev/null 2>&1; then
  echo ""
  echo "  A 12-digit number is being committed. If that is an AWS account ID,"
  echo "  replace it with a variable or the 000000000000 placeholder."
  echo ""
  if ( : < /dev/tty ) 2>/dev/null; then
    read -r -p "  Continue anyway? [y/N] " ok < /dev/tty
    [[ "$ok" == "y" ]] || exit 1
  else
    echo "  No terminal to ask (an IDE or a tool is committing): blocked."
    echo "  Replace the number, or commit from a terminal and answer the prompt."
    exit 1
  fi
fi
EOF

install_hook "$HOOKS/commit-msg" <<'EOF'
#!/usr/bin/env bash
# thalam-managed hook
# Thalam commit-msg — the commit convention, checked before the commit exists (SPEC-001-R5).

set -euo pipefail

# The first interpreter that actually runs: on Windows `python3` can be a Store stub that fails.
PY=""
for cand in python3 python "py -3"; do
  # shellcheck disable=SC2086  # "py -3" is a command and its argument
  if $cand -c 'import sys' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "  WARNING: no working python found — commit message NOT checked (CI still checks it)."
  exit 0
fi
BRANCH="$(git symbolic-ref --short -q HEAD || true)"
# shellcheck disable=SC2086
exec $PY scripts/dev/check_commits.py --file "$1" --branch "$BRANCH"
EOF
