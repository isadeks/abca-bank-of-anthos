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
| e2e (Cypress) | `e2e/` | JavaScript | runs against a deployed environment |

## Check before you push
- `mise run check` runs what CI checks without a cluster, for the services you changed: their unit tests, the build (Java `package`, Python lockfile + import), and CI's rule gates (a source change needs a test; changing an existing test needs approval). Fix until it passes.
- `mise run test` runs only the unit tests (`ALL=1` for every service).
- Python tests import the service as a package (`from contacts.contacts import create_app`), so they run from the service directory with `PYTHONPATH=..`. Follow the existing tests' mocking style (`mock_open` for the key file, patched `os.environ`).

## What CI checks on every pull request
CI runs outside this repository; changing scripts here does not change it.
- `abca-boa/ci`: the unit tests of every changed service, then its image build.
- `abca-boa/tests`: a change to a service's source must add or change a test.
- `abca-boa/test-integrity`: editing or deleting an existing test needs a maintainer's approval. Add new test files or new test cases instead of changing existing ones.
- `abca-boa/integration`: integration tests run against the **real database images** (Postgres with the Bank of Anthos schema and demo data), in CI only:
  - Python: `src/<service>/tests/integration/*.py`, reading `ACCOUNTS_DB_URI` (accounts-db). Import the service's modules as production does (`from db import ContactsDb`).
  - Java: test classes named `*IT.java` under `src/test/java`, using `SPRING_DATASOURCE_URL` / `_USERNAME` / `_PASSWORD` (ledger-db). Unit runs skip `*IT`.
  - They are not part of `mise run check` (no database locally); CI reports them on the PR.
- `abca-boa/ui-check`: **your own UI check of the change**, run on the preview (see "UI checks" below). Required when a frontend template or static file changes (a UI change); its video and screenshots are posted on the PR and in the Linear session.
- `abca-boa/e2e`: the Cypress suite in `e2e/` (login, signup, deposit, transfer, home) runs against the preview. Add new specs under `e2e/cypress/integration/`; changing an existing spec needs a maintainer's approval like any existing test.
- `deployment:Preview`: when the PR changes a service's code, the manifests, `deploy/` or `e2e/`, it is deployed to its own namespace `pr-<N>` (changed services built from the PR, the rest from production) and smoke-tested: login, home page (balance, history, contacts), and a deposit that must change the balance.

A change to tests or docs only gets no preview, and merging it leaves production as it is. Merging anything else to `main` releases to production: the changed services are built, deployed, smoke-tested, and rolled back automatically on failure.

## Conventions
- Each service is a directory under `src/` with a `Dockerfile` (or a Jib `pom.xml`). Its Kubernetes manifest lives in `kubernetes-manifests/<name>.yaml`, listed in `kubernetes-manifests/kustomization.yaml`.
- **A new service** uses `image: abca-boa/<name>` in its manifest; CI creates the image repository and fills in the registry and tag.
- Service-to-service addresses come from the `service-api-config` ConfigMap (`kubernetes-manifests/config.yaml`).
- Telemetry: all services export over OpenTelemetry (OTLP) and telemetry is enabled on EKS; the GCP exporters (Cloud Trace, Stackdriver) are gone. New telemetry uses OpenTelemetry with OTLP, not a vendor-specific exporter.
  - Every environment (production `boa` and each `pr-<N>`) has an OpenTelemetry collector at `otel-collector.observability.svc.cluster.local`: OTLP gRPC on `:4317`, HTTP on `:4318`. It sends traces to AWS X-Ray and metrics to CloudWatch (namespace `BankOfAnthos`).
  - Configure services with the standard variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`) in the manifests, and include `k8s.namespace.name` (from the downward API) so a preview's traces can be told apart from production's.
  - Use W3C trace context (`traceparent`) between services.
- Never commit secrets, account ids or IP addresses; `deploy/eks/apply.sh` fills in environment-specific values.

## UI checks (`.abca/ui-checks/*.spec.ts`)
When you change what a user sees, add a Playwright check that shows the change working. CI runs it against your PR's preview, records a video and turns your steps into a captioned walk-through that reviewers watch on the PR and in Linear.
- One file per change at the top level of `.abca/ui-checks/` (files in sub-folders don't run). Use `@playwright/test` and the CI helper `./ui-annotate` only.
- Environment: `PREVIEW_URL` (Playwright's `baseURL`, so `page.goto('/home')` works), `DEMO_USER` / `DEMO_PASSWORD` (the demo account `testuser` / `bankofanthos`, which has demo transactions and contacts). If you need an empty account, sign up a new user through `/signup` with a unique name.
- A good check: `await signIn(page)` → drive the UI to your change → 2–6 steps, each `await highlight(page, el, 'short label')` then `await shot(page, 'Caption a reviewer reads', { focus: el })` → **assert** the behaviour with `expect`. Captions describe what the user sees ("Spending by category on the home page"), not test internals.
- Stable selectors: the templates' ids (`#current-balance`, `#transaction-table`, `#deposit-form`, `#payment-form`, …); add an `id` or `data-testid` to new elements you need to find.
- 120 s per test, no retries. An example: `.abca/ui-checks/examples/home-balance.spec.ts`.

