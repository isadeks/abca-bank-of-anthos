#!/usr/bin/env bash
# Run the unit tests of every service changed against the base branch (ALL=1: every service).
#   scripts/test-changed.sh            # what CI will test for this branch
#   ALL=1 scripts/test-changed.sh
# Python services: uv + pytest (tests/ next to the service). Java services: ./mvnw test for that module.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
BASE="${BASE:-origin/main}"
[ "$BASE" = origin/main ] && { git fetch -q origin main 2>/dev/null || true; }
if [ "${ALL:-0}" = 1 ]; then changed=$(git ls-files); else
  changed=$( { git diff --name-only "$(git merge-base "$BASE" HEAD)"; git diff --name-only; git ls-files --others --exclude-standard; } | sort -u); fi
svc_dirs=$(git ls-files 'src/**/Dockerfile' 'src/**/pom.xml' | xargs -n1 dirname | sort -u | grep -v -e ledgermonolith -e '^src/\(accounts\|ledger\)$' || true)
java=() ; rc=0 ; ran=0
for d in $svc_dirs; do
  hit=0; echo "$changed" | grep -q "^$d/" && hit=1
  [ -f "$d/pom.xml" ] && echo "$changed" | grep -qE '^(pom.xml|mvnw|\.mvn/)' && hit=1
  [ $hit = 1 ] || continue
  if [ -f "$d/pom.xml" ]; then java+=("$d")
  elif [ -f "$d/pyproject.toml" ]; then
    if ls "$d"/tests/*.py >/dev/null 2>&1; then
      echo "== $d (pytest)"; ran=1
      (cd "$d" && uv sync -q --frozen && PYTHONPATH=.. uv run pytest -q) || rc=1
    else echo "== $d: no tests/ yet (add them: CI requires a test with every source change)"; fi
  fi
done
if [ ${#java[@]} -gt 0 ]; then
  echo "== ${java[*]} (maven)"; ran=1
  ./mvnw -B -q -pl "$(IFS=,; echo "${java[*]}")" -am test || rc=1
fi
[ $ran = 1 ] || echo "no service with tests changed"
exit $rc
