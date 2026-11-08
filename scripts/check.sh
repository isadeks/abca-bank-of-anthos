#!/usr/bin/env bash
# The pre-push check: everything CI checks that can run without a cluster, for the services changed
# against main (ALL=1: every service). Fix until it passes; CI then adds image builds, the preview,
# the smoke test and the e2e suite.
#   1. unit tests of the changed services            (CI: abca-boa/ci)
#   2. build: Java modules package, Python lockfiles are current and every service imports
#   3. CI's rule gates, checked early:
#        a source change needs a test                (CI: abca-boa/tests)
#        changing an existing test needs approval    (CI: abca-boa/test-integrity)
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
BASE="${BASE:-origin/main}"; [ "$BASE" = origin/main ] && { git fetch -q origin main 2>/dev/null || true; }
MB="$(git merge-base "$BASE" HEAD 2>/dev/null || echo HEAD)"
rc=0; fail() { echo "✘ $*"; rc=1; }; ok() { echo "✔ $*"; }

echo "== 1. unit tests"; scripts/test-changed.sh || fail "unit tests"

echo "== 2. build"
if [ "${ALL:-0}" = 1 ]; then changed=$(git ls-files); else
  changed=$( { git diff --name-only "$MB"; git diff --name-only; git ls-files --others --exclude-standard; } | sort -u); fi
java=()
for d in $(git ls-files 'src/**/pom.xml' 'src/**/pyproject.toml' | xargs -n1 dirname | sort -u | grep -v ledgermonolith); do
  hit=0; echo "$changed" | grep -q "^$d/" && hit=1
  [ -f "$d/pom.xml" ] && echo "$changed" | grep -qE '^(pom.xml|mvnw|\.mvn/)' && hit=1
  [ $hit = 1 ] || continue
  if [ -f "$d/pom.xml" ]; then java+=("$d")
  else
    name=$(basename "$d")
    (cd "$d" && uv lock --check -q) && ok "$d: uv.lock matches pyproject.toml" || fail "$d: uv.lock is stale (run: cd $d && uv lock)"
    mod=$(ls "$d"/*.py 2>/dev/null | xargs -n1 basename | grep -vE '^(__init__|db|api_call|traced_thread_pool_executor|locustfile)\.py$' | head -1); mod="${mod%.py}"
    if [ -n "$mod" ] && [ "$name" != loadgenerator ]; then
      (cd "$d" && uv sync -q --frozen && uv run python -c "import $mod") && ok "$d: imports like production ($mod)" || fail "$d: import $mod failed (production runs gunicorn $mod:create_app())"
    fi
  fi
done
if [ ${#java[@]} -gt 0 ]; then
  ./mvnw -B -q -pl "$(IFS=,; echo "${java[*]}")" -am -DskipTests package && ok "java: ${java[*]} package" || fail "java package"
fi

echo "== 3. CI rule gates (against $BASE)"
files=$(git diff --name-status "$MB"; git status --porcelain | awk '{print ($1=="??"?"A":$1)"\t"$2}')
is_test() { echo "$1" | grep -qE '/tests/|/src/test/|(^|/)test_[^/]*$|^e2e/cypress/|\.abca/ui-checks/'; }
src=0; tests=0; changed_tests=()
while IFS=$'\t' read -r st f rest; do
  [ -n "${f:-}" ] || continue; [ -n "${rest:-}" ] && f="$rest"
  if is_test "$f"; then tests=$((tests+1)); case "$st" in A*) ;; *) changed_tests+=("$st $f");; esac
  elif [[ "$f" == src/* && "$f" != *.md ]]; then src=$((src+1)); fi
done <<<"$(echo "$files" | sort -u)"
if [ $src -gt 0 ] && [ $tests = 0 ]; then fail "$src source file(s) changed but no test added or changed: CI's abca-boa/tests will fail"
else ok "tests gate: $src source file(s), $tests test file(s)"; fi
if [ ${#changed_tests[@]} -gt 0 ]; then
  echo "! existing test files changed (CI's abca-boa/test-integrity will wait for a maintainer's approval):"
  printf '    %s\n' "${changed_tests[@]}"
  echo "  Prefer new test files or new test cases. If the change is required, say why in the PR description."
else ok "no existing test changed"; fi
exit $rc
