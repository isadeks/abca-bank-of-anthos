/*
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.Appender;
import org.apache.logging.log4j.core.Layout;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.actuate.autoconfigure.observation.ObservationAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.opentelemetry.OpenTelemetryAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.MicrometerTracingAutoConfiguration;
import org.springframework.boot.actuate.autoconfigure.tracing.OpenTelemetryTracingAutoConfiguration;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

/**
 * A log line written while a span is active carries that span's trace_id and
 * span_id, and leaves both empty when no span is active. The line is rendered
 * with the layout of the real log4j2.xml, and the ids reach it through the
 * traceId / spanId keys that Micrometer tracing puts in the SLF4J MDC.
 */
class LogTraceIdsTest {

    private static final Logger LOGGER =
        LoggerFactory.getLogger(LogTraceIdsTest.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final List<String> lines = new CopyOnWriteArrayList<>();
    private Appender capture;

    /** The tracing auto-configurations a service gets from Spring Boot. */
    @org.springframework.context.annotation.Configuration(proxyBeanMethods = false)
    @ImportAutoConfiguration({
        OpenTelemetryAutoConfiguration.class,
        OpenTelemetryTracingAutoConfiguration.class,
        MicrometerTracingAutoConfiguration.class,
        ObservationAutoConfiguration.class})
    static class TracingConfiguration {
    }

    /**
     * Taps the console appender's layout. Done after the application has
     * started, because starting it configures logging from log4j2.xml.
     */
    private void captureLogLines() {
        LoggerContext context = (LoggerContext) LogManager.getContext(false);
        Configuration config = context.getConfiguration();
        Appender console = config.getAppender("console");
        assertNotNull(console, "log4j2.xml has no console appender");
        Layout<?> layout = console.getLayout();
        capture = new AbstractAppender("capture", null, null, true, Property.EMPTY_ARRAY) {
            @Override
            public void append(LogEvent event) {
                lines.add(layout.toSerializable(event).toString());
            }
        };
        capture.start();
        config.getRootLogger().addAppender(capture, null, null);
        context.updateLoggers();
    }

    @AfterEach
    void releaseLogLines() {
        if (capture == null) {
            return;
        }
        LoggerContext context = (LoggerContext) LogManager.getContext(false);
        LoggerConfig root = context.getConfiguration().getRootLogger();
        root.removeAppender("capture");
        capture.stop();
        context.updateLoggers();
    }

    @Test
    @DisplayName("Given an active span, the log line has its trace_id and span_id")
    void logLineInsideSpanCarriesIds() throws Exception {
        // A SpringApplication, not an ApplicationContextRunner: only it
        // registers the listener that copies the span ids into the MDC.
        try (ConfigurableApplicationContext context =
                 new SpringApplicationBuilder(TracingConfiguration.class)
                     .web(WebApplicationType.NONE)
                     .properties("ENABLE_TRACING=true")
                     .run()) {
            captureLogLines();
            Tracer tracer = context.getBean(Tracer.class);
            Span span = tracer.nextSpan().name("incoming-request").start();
            try (Tracer.SpanInScope ignored = tracer.withSpan(span)) {
                LOGGER.info("inside a span");
            } finally {
                span.end();
            }

            JsonNode line = lineWithMessage("inside a span");
            assertEquals(span.context().traceId(), line.get("trace_id").asText());
            assertEquals(span.context().spanId(), line.get("span_id").asText());
            assertFalse(line.get("trace_id").asText().isEmpty());
            assertFalse(line.get("span_id").asText().isEmpty());
        }
    }

    @Test
    @DisplayName("Given no active span, trace_id and span_id are empty")
    void logLineOutsideSpanHasEmptyIds() throws Exception {
        captureLogLines();
        LOGGER.info("outside a span");

        JsonNode line = lineWithMessage("outside a span");
        assertTrue(line.get("trace_id").asText().isEmpty());
        assertTrue(line.get("span_id").asText().isEmpty());
    }

    private JsonNode lineWithMessage(String message) throws Exception {
        for (String line : lines) {
            if (line.contains(message)) {
                return MAPPER.readTree(line);
            }
        }
        throw new AssertionError("no log line containing '" + message + "' in " + lines);
    }
}
