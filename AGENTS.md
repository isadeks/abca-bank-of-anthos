# Working on this repository

Bank of Anthos is a demo bank: 6 services, 2 Postgres databases and a load generator, deployed to Amazon EKS from `deploy/eks`.

| Service | Path | Language | Tests |
|---|---|---|---|
| frontend | `src/frontend` | Python (Flask) | `tests/` (none yet) |
| userservice | `src/accounts/userservice` | Python (Flask) | `tests/` |
| contacts | `src/accounts/contacts` | Python (Flask) | `tests/` |
| ledgerwriter | `src/ledger/ledgerwriter` | Java 17 (Spring Boot) | `src/test/java` |
| balancereader | `src/ledger/balancereader` | Java 17 (Spring Boot) | `src/test/java` |
| transactionhistory | `src/ledger/transactionhistory` | Java 17 (Spring Boot) | `src/test/java` |
| accounts-db, ledger-db | `src/accounts/accounts-db`, `src/ledger/ledger-db` | Postgres images | – |
| loadgenerator | `src/loadgenerator` | Python (Locust) | – |

## Test before you push
- `mise run test` runs the unit tests of every service you changed (Python: uv + pytest; Java: `./mvnw test` for that module). `ALL=1 mise run test` runs all of them.
- Python tests import the service as a package (`from contacts.contacts import create_app`), so they run from the service directory with `PYTHONPATH=..`. Follow the existing tests' mocking style (`mock_open` for the key file, patched `os.environ`).

## What CI checks on every pull request
CI runs outside this repository; changing scripts here does not change it.
- `abca-boa/ci`: the unit tests of every changed service, then its image build.
- `abca-boa/tests`: a change to a service's source must add or change a test.
- `abca-boa/test-integrity`: editing or deleting an existing test needs a maintainer's approval. Add new test files or new test cases instead of changing existing ones.
- `deployment:Preview`: the PR is deployed to its own namespace `pr-<N>` (changed services built from the PR, the rest from production) and smoke-tested: login, home page (balance, history, contacts), and a deposit that must change the balance.

Merging to `main` releases to production: the changed services are built, deployed, smoke-tested, and rolled back automatically on failure.

## Conventions
- Each service is a directory under `src/` with a `Dockerfile` (or a Jib `pom.xml`). Its Kubernetes manifest lives in `kubernetes-manifests/<name>.yaml`, listed in `kubernetes-manifests/kustomization.yaml`.
- **A new service** uses `image: abca-boa/<name>` in its manifest; CI creates the image repository and fills in the registry and tag.
- Service-to-service addresses come from the `service-api-config` ConfigMap (`kubernetes-manifests/config.yaml`).
- Telemetry: the GCP exporters are switched off on EKS (`deploy/eks/telemetry-off.yaml`). New telemetry uses OpenTelemetry with OTLP, not a vendor-specific exporter.
  - Every environment (production `boa` and each `pr-<N>`) has an OpenTelemetry collector at `otel-collector.observability.svc.cluster.local`: OTLP gRPC on `:4317`, HTTP on `:4318`. It sends traces to AWS X-Ray and metrics to CloudWatch (namespace `BankOfAnthos`).
  - Configure services with the standard variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`) in the manifests, and include `k8s.namespace.name` (from the downward API) so a preview's traces can be told apart from production's.
  - Use W3C trace context (`traceparent`) between services.
- Never commit secrets, account ids or IP addresses; `deploy/eks/apply.sh` fills in environment-specific values.
