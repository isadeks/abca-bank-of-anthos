# Bank of Anthos on Amazon EKS

This overlay runs the upstream manifests on EKS Auto Mode:

- **Namespace** `boa`.
- **Telemetry on.** Every service exports OpenTelemetry (OTLP) to the environment's collector at `otel-collector.observability.svc.cluster.local` (gRPC `:4317` for the Python services, HTTP `:4318` for the Java services). The collector sends traces to AWS X-Ray and metrics to CloudWatch (namespace `BankOfAnthos`). Trace context is W3C `traceparent`, and every span carries `k8s.namespace.name` (`boa` or `pr-<N>`). `ENABLE_TRACING` / `ENABLE_METRICS` come from the base manifests; there is no EKS override.
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

## Checking telemetry

One login plus one deposit should show as a single connected trace:

1. Open the frontend of the environment (`boa` or a `pr-<N>` preview), sign in as `testuser` / `bankofanthos` and make one deposit.
2. In the AWS console open CloudWatch, then X-Ray traces, and filter on the namespace, for example `annotation`/resource attribute `k8s.namespace.name = "pr-12"` (or `boa`), within the last few minutes.
3. Open the traces: the login is one trace `frontend` then `userservice`; the deposit is one trace `frontend` then `ledgerwriter`, followed by `balancereader` / `transactionhistory` when the home page reloads. Each trace has a single trace id across all services, with no orphaned root spans for the downstream services.
4. Metrics from the Java services appear in CloudWatch under the `BankOfAnthos` namespace.
