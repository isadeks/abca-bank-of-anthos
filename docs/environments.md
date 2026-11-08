# Running in Kubernetes Environments

## GKE

Use the default instructions in the [README](/README.md). When Workload Identity is enabled, use the [Workload Identity instructions](/docs/workload-identity.md).

## Non-GKE Kubernetes Clusters

Bank of Anthos was designed to work on any Kubernetes cluster and has no cloud-specific requirements. All services emit telemetry with vendor-neutral [OpenTelemetry](https://opentelemetry.io/): traces from every service (and metrics from the Java services) are exported over OTLP, and trace context is propagated between services with the W3C `traceparent` header. No cloud credentials are needed by the services themselves.

Each Deployment is configured with the standard OpenTelemetry variables:

- `OTEL_EXPORTER_OTLP_ENDPOINT`: the OTLP endpoint of your OpenTelemetry collector (gRPC `:4317` for the Python services, HTTP `:4318` for the Java services).
- `OTEL_SERVICE_NAME`: the service name shown on spans.
- `OTEL_RESOURCE_ATTRIBUTES`: includes `k8s.namespace.name`, taken from the downward API, so that environments sharing a collector can be told apart.

**To turn off telemetry export**: set `ENABLE_TRACING=false` (and `ENABLE_METRICS=false` for the Java services) in each Deployment YAML.

**To export telemetry to your own backend**: run an OpenTelemetry collector (or any OTLP-compatible endpoint) that forwards to your backend of choice, point `OTEL_EXPORTER_OTLP_ENDPOINT` at it, and deploy with `ENABLE_TRACING` and `ENABLE_METRICS` set to `true`. On Amazon EKS see [deploy/eks](/deploy/eks/README.md), which sends traces to AWS X-Ray and metrics to CloudWatch.
