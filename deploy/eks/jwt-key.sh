#!/usr/bin/env bash
# Creates the JWT signing key pair as the `jwt-key` Secret in namespace boa.
# The key is generated here and never committed (upstream ships a published demo key).
set -euo pipefail
NS="${1:-boa}"
if kubectl -n "$NS" get secret jwt-key >/dev/null 2>&1; then echo "jwt-key already exists in $NS"; exit 0; fi
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
openssl genrsa -out "$d/jwtRS256.key" 4096 2>/dev/null
openssl rsa -in "$d/jwtRS256.key" -outform PEM -pubout -out "$d/jwtRS256.key.pub" 2>/dev/null
kubectl -n "$NS" create secret generic jwt-key \
  --from-file=jwtRS256.key="$d/jwtRS256.key" --from-file=jwtRS256.key.pub="$d/jwtRS256.key.pub"
