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

package anthos.samples.bankofanthos.ledgerwriter;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.autoconfigure.observation.ObservationAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.observation.web.client.HttpClientObservationsAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.opentelemetry.OpenTelemetryAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.MicrometerTracingAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.OpenTelemetryTracingAutoConfiguration;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.http.HttpMessageConvertersAutoConfiguration;
import org.springframework.boot.autoconfigure.web.client.RestTemplateAutoConfiguration;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.web.client.RestTemplate;

/**
 * The RestTemplate that calls balancereader must carry the W3C trace context,
 * so that the call joins the trace of the request being served.
 */
class TracePropagationTest {

    private final AtomicReference<String> traceparent = new AtomicReference<>();
    private HttpServer balanceReader;

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withInitializer(new ConfigDataApplicationContextInitializer())
        .withConfiguration(AutoConfigurations.of(
            OpenTelemetryAutoConfiguration.class,
            OpenTelemetryTracingAutoConfiguration.class,
            MicrometerTracingAutoConfiguration.class,
            ObservationAutoConfiguration.class,
            HttpClientObservationsAutoConfiguration.class,
            HttpMessageConvertersAutoConfiguration.class,
            RestTemplateAutoConfiguration.class));

    @BeforeEach
    void startBalanceReader() throws IOException {
        balanceReader = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        balanceReader.createContext("/balances", exchange -> {
            traceparent.set(exchange.getRequestHeaders().getFirst("traceparent"));
            byte[] body = "100".getBytes();
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        balanceReader.start();
    }

    @AfterEach
    void stopBalanceReader() {
        balanceReader.stop(0);
    }

    @Test
    @DisplayName("Given a request being traced, the RestTemplate call "
        + "carries a traceparent header of the same trace")
    void restTemplateForwardsTraceContext() {
        runner.withPropertyValues("ENABLE_TRACING=true").run(context -> {
            RestTemplate restTemplate = new LedgerWriterApplication()
                .restTemplate(context.getBean(RestTemplateBuilder.class));
            Tracer tracer = context.getBean(Tracer.class);

            Span span = tracer.nextSpan().name("incoming-request").start();
            try (Tracer.SpanInScope ignored = tracer.withSpan(span)) {
                String url = "http://127.0.0.1:"
                    + balanceReader.getAddress().getPort() + "/balances/1234567890";
                assertEquals("100", restTemplate.getForObject(url, String.class));
            } finally {
                span.end();
            }

            assertNotNull(traceparent.get(), "no traceparent header was sent");
            assertTrue(traceparent.get().startsWith(
                "00-" + span.context().traceId() + "-"),
                "traceparent " + traceparent.get()
                    + " is not in trace " + span.context().traceId());
        });
    }
}
