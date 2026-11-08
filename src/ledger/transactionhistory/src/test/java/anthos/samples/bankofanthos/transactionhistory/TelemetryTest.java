/*
 * Copyright 2026, Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.registry.otlp.OtlpMeterRegistry;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import io.micrometer.tracing.propagation.Propagator;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.SpanExporter;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.autoconfigure.metrics.CompositeMeterRegistryAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.metrics.MetricsAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.metrics.export.otlp.OtlpMetricsExportAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.metrics.export.simple.SimpleMetricsExportAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.observation.ObservationAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.opentelemetry.OpenTelemetryAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.MicrometerTracingAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.NoopTracerAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.OpenTelemetryTracingAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.otlp.OtlpTracingAutoConfiguration;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

/**
 * Checks the telemetry wiring of the service: traces and metrics are exported
 * over OTLP to the collector, carry the k8s.namespace.name resource attribute,
 * use W3C trace context, and honour the ENABLE_TRACING / ENABLE_METRICS
 * switches. The real application.properties is loaded; the collector is a
 * local HTTP server standing in for the cluster's OpenTelemetry collector.
 */
class TelemetryTest {

    private static final String NAMESPACE_KEY = "k8s.namespace.name";
    private static final String NAMESPACE = "pr-42";
    private static final String SERVICE_NAME = "transactionhistory";
    private static final String TRACE_ID = "0af7651916cd43dd8448eb211c80319c";
    private static final String TRACEPARENT =
        "00-" + TRACE_ID + "-b7ad6b7169203331-01";

    private final List<String[]> received = new CopyOnWriteArrayList<>();
    private final List<byte[]> bodies = new CopyOnWriteArrayList<>();
    private HttpServer collector;

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withInitializer(new ConfigDataApplicationContextInitializer())
        .withConfiguration(AutoConfigurations.of(
            OpenTelemetryAutoConfiguration.class,
            OpenTelemetryTracingAutoConfiguration.class,
            OtlpTracingAutoConfiguration.class,
            MicrometerTracingAutoConfiguration.class,
            NoopTracerAutoConfiguration.class,
            ObservationAutoConfiguration.class,
            MetricsAutoConfiguration.class,
            CompositeMeterRegistryAutoConfiguration.class,
            OtlpMetricsExportAutoConfiguration.class,
            SimpleMetricsExportAutoConfiguration.class));

    @BeforeEach
    void startCollector() throws IOException {
        collector = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        collector.createContext("/", exchange -> {
            byte[] body = exchange.getRequestBody().readAllBytes();
            received.add(new String[] {exchange.getRequestURI().getPath()});
            bodies.add(body);
            exchange.sendResponseHeaders(200, -1);
            exchange.close();
        });
        collector.start();
    }

    @AfterEach
    void stopCollector() {
        collector.stop(0);
    }

    private String[] properties(String... extra) {
        String endpoint = "http://127.0.0.1:" + collector.getAddress().getPort();
        // OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES are read from the
        // process environment, which surefire sets (see pom.xml).
        String[] base = {"OTEL_EXPORTER_OTLP_ENDPOINT=" + endpoint};
        String[] all = new String[base.length + extra.length];
        System.arraycopy(base, 0, all, 0, base.length);
        System.arraycopy(extra, 0, all, base.length, extra.length);
        return all;
    }

    /** Whether an OTLP request to the given path carried all the strings. */
    private boolean received(String path, String... expected) {
        for (int i = 0; i < received.size(); i++) {
            if (!received.get(i)[0].equals(path)) {
                continue;
            }
            String body = new String(bodies.get(i), StandardCharsets.ISO_8859_1);
            boolean all = true;
            for (String e : expected) {
                all &= body.contains(e);
            }
            if (all) {
                return true;
            }
        }
        return false;
    }

    /** The OTLP requests received so far, for assertion messages. */
    private String dump() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < received.size(); i++) {
            sb.append(received.get(i)[0]).append(' ').append(
                new String(bodies.get(i), StandardCharsets.ISO_8859_1)
                    .replaceAll("[^\\x20-\\x7e]", "."));
        }
        return sb.toString();
    }

    @Test
    @DisplayName("Spans are sent to the collector over OTLP and carry "
        + "the service name and k8s.namespace.name")
    void spansCarryNamespace() {
        runner.withPropertyValues(properties()).run(context -> {
            Tracer tracer = context.getBean(Tracer.class);
            Span span = tracer.nextSpan().name("telemetry-test-span").start();
            span.end();
            context.getBean(SdkTracerProvider.class)
                .forceFlush().join(10, TimeUnit.SECONDS);

            assertTrue(received("/v1/traces", "telemetry-test-span",
                NAMESPACE_KEY, NAMESPACE, SERVICE_NAME),
                "collector did not receive a span with the namespace attribute: " + dump());
        });
    }

    @Test
    @DisplayName("Metrics are sent to the collector over OTLP and carry "
        + "the service name and k8s.namespace.name")
    void metricsCarryNamespace() {
        runner.withPropertyValues(properties()).run(context -> {
            OtlpMeterRegistry registry = context.getBean(OtlpMeterRegistry.class);
            registry.counter("telemetry.test.counter").increment();
            registry.close(); // pushes a final batch

            assertTrue(received("/v1/metrics", "telemetry.test.counter",
                NAMESPACE_KEY, NAMESPACE, SERVICE_NAME),
                "collector did not receive a metric with the namespace attribute: "
                + dump());
        });
    }

    @Test
    @DisplayName("Every span is sampled")
    void everySpanIsSampled() {
        runner.withPropertyValues(properties()).run(context -> {
            Tracer tracer = context.getBean(Tracer.class);
            for (int i = 0; i < 20; i++) {
                Span span = tracer.nextSpan().name("sampled").start();
                assertTrue(Boolean.TRUE.equals(span.context().sampled()));
                span.end();
            }
        });
    }

    @Test
    @DisplayName("Incoming W3C traceparent is accepted and forwarded "
        + "in the same trace")
    void w3cTraceContextIsAcceptedAndForwarded() {
        runner.withPropertyValues(properties()).run(context -> {
            Propagator propagator = context.getBean(Propagator.class);
            Map<String, String> incoming = new HashMap<>();
            incoming.put("traceparent", TRACEPARENT);

            Span span = propagator.extract(incoming, Map<String, String>::get)
                .name("child").start();
            assertEquals(TRACE_ID, span.context().traceId());

            Map<String, String> outgoing = new HashMap<>();
            propagator.inject(span.context(), outgoing, Map::put);
            span.end();
            assertTrue(outgoing.containsKey("traceparent"));
            assertTrue(outgoing.get("traceparent")
                .startsWith("00-" + TRACE_ID + "-"));
        });
    }

    @Test
    @DisplayName("Given ENABLE_TRACING=false, no span exporter is created")
    void tracingCanBeDisabled() {
        runner.withPropertyValues(properties("ENABLE_TRACING=false"))
            .run(context -> {
                assertTrue(context.getBeansOfType(SpanExporter.class).isEmpty());
            });
    }

    @Test
    @DisplayName("Given ENABLE_METRICS=false, nothing is exported but a "
        + "MeterRegistry can still be injected")
    void metricsCanBeDisabled() {
        runner.withPropertyValues(properties("ENABLE_METRICS=false"))
            .run(context -> {
                assertTrue(context.getBeansOfType(OtlpMeterRegistry.class)
                    .isEmpty());
                assertEquals(1, context.getBeansOfType(MeterRegistry.class).size());
            });
    }

    @Test
    @DisplayName("Given neither switch is set, tracing and metrics are on")
    void tracingAndMetricsAreOnByDefault() {
        runner.withPropertyValues(properties()).run(context -> {
            assertEquals(1, context.getBeansOfType(SpanExporter.class).size());
            assertEquals(1, context.getBeansOfType(OtlpMeterRegistry.class).size());
        });
    }
}
