# Bank of Anthos on Amazon EKS

This overlay runs the upstream manifests on EKS Auto Mode:

- **Namespace** `boa`.
- **Telemetry off.** The GCP-only exporters (Cloud Trace, Stackdriver) need a GCP project, so `ENABLE_TRACING` and `ENABLE_METRICS` are `false`. Moving to OpenTelemetry (OTLP → ADOT → X-Ray and CloudWatch) is tracked as its own work.
- **No GKE Workload Identity** annotation on the service account.
- **Frontend** behind an internet-facing NLB that only accepts the CIDRs in `frontend-lb.yaml`.
- **JWT key** generated per namespace by `jwt-key.sh`; it is never committed.
- **No account-specific values** in the repo: `apply.sh` fills in the registry and the allow-list.

```bash
export REGISTRY=<account>.dkr.ecr.<region>.amazonaws.com   # images live in <REGISTRY>/abca-boa/<service>
export BOA_ALLOW_CIDRS="203.0.113.10/32"                  # who may reach the frontend
deploy/eks/apply.sh                       # production, namespace boa
deploy/eks/apply.sh pr-12 frontend=pr-12-ab12cd3   # a PR preview with one image overridden
kubectl -n boa get svc frontend           # EXTERNAL-IP is the NLB hostname
```

Demo login: `testuser` / `bankofanthos`.
