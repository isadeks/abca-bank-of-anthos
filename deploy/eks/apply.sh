#!/usr/bin/env bash
# Renders deploy/eks for one environment and applies it.
#   REGISTRY=<acct>.dkr.ecr.<region>.amazonaws.com BOA_ALLOW_CIDRS="1.2.3.4/32,5.6.7.0/24" \
#   deploy/eks/apply.sh [namespace] [service=tag ...]
# namespace defaults to boa (production). Each service=tag overrides one image tag (e.g. frontend=pr-12-ab12cd3).
set -euo pipefail
: "${REGISTRY:?set REGISTRY}" "${BOA_ALLOW_CIDRS:?set BOA_ALLOW_CIDRS}"
NS="${1:-boa}"; shift || true
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../.." && pwd)"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
mkdir -p "$work/deploy" && cp -r "$here" "$work/deploy/eks" && cp -r "$root/kubernetes-manifests" "$work/"
k="$work/deploy/eks/kustomization.yaml"
sed -i "s#REGISTRY/#${REGISTRY}/#; s#^namespace: boa#namespace: ${NS}#" "$k"
sed -i "s#^  name: boa\$#  name: ${NS}#" "$work/deploy/eks/namespace.yaml"
python3 - "$work/deploy/eks/frontend-lb.yaml" "$BOA_ALLOW_CIDRS" <<'PY'
import sys
p, cidrs = sys.argv[1], [c.strip() for c in sys.argv[2].split(",") if c.strip()]
s = open(p).read()
line = [l for l in s.splitlines() if "replaced by apply.sh" in l][0]
open(p, "w").write(s.replace(line, "\n".join(f"    - {c}" for c in cidrs)))
PY
for o in "$@"; do svc="${o%%=*}"; tag="${o#*=}"
  python3 - "$k" "$svc" "$tag" <<'PY'
import sys, re
p, svc, tag = sys.argv[1:]
s = open(p).read()
s2 = re.sub(rf"(newName: [^\n]*/abca-boa/{re.escape(svc)}\n    newTag: )\S+", rf"\g<1>{tag}", s)
if s2 == s:  # a service added after the upstream nine: its manifest uses image abca-boa/<svc>
    reg = re.search(r"newName: ([^\n]*)/abca-boa/", s).group(1)
    s2 = s.rstrip("\n") + f"\n  - name: abca-boa/{svc}\n    newName: {reg}/abca-boa/{svc}\n    newTag: {tag}\n"
open(p, "w").write(s2)
PY
done
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
"$here/jwt-key.sh" "$NS"
kubectl apply -k "$work/deploy/eks"
