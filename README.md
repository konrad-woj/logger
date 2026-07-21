# Structured logger

Thin wrapper around [structlog](https://www.structlog.org/) that gives coloured console output in development and machine-readable JSON in production.

## Environment variables

| Variable       | Values                                                                                             | Default     |
|----------------|----------------------------------------------------------------------------------------------------|-------------|
| `LOG_ENV`      | `production` → JSON, anything else → console                                                       | dev console |
| `LOG_LEVEL`    | stdlib level name (`DEBUG`, `INFO`, `WARNING`, …)                                                  | `INFO`      |
| `LOG_PROVIDER` | `generic`, `gcp`, `aws`, `azure` — see [Cloud provider integrations](#cloud-provider-integrations) | `generic`   |

## Usage

### 1 — Configure once at startup

Call `configure_logging()` **once**, before any logger is used — typically in `main.py` or a FastAPI lifespan handler.

```python
from logger import configure_logging

configure_logging()
```

### 2 — Get a logger in each module

```python
from logger import get_logger

log = get_logger(__name__)
```

### 3 — Log with structured key-value context

```python
log.info("document.converted", path="/tmp/report.pdf", pages=42)
log.warning("chunk.empty", doc_id="abc123")
log.error("embedding.failed", doc_id="abc123", exc_info=True)
log.exception("embedding.failed", doc_id="abc123")  
```

---

## Development output

With `LOG_ENV` unset (or anything other than `production`) you get coloured, human-readable output:

```
2024-01-05T12:00:00.000000Z [info     ] document.converted  [myapp.orders] pages=42 path=/tmp/report.pdf
2024-01-05T12:00:00.001000Z [warning  ] chunk.empty         [myapp.tasks] doc_id=abc123
```

Set `LOG_LEVEL=DEBUG` to see debug messages:

```bash
LOG_LEVEL=DEBUG uv run python main.py
```

## Production output

Set `LOG_ENV=production` to switch to newline-delimited JSON (one object per line), suitable for log aggregators such as Datadog, Loki, or CloudWatch:

```bash
LOG_ENV=production LOG_LEVEL=INFO uv run python main.py
```

Each log line is a JSON object:

```json
{"level": "info", "logger": "myapp.orders", "timestamp": "2024-01-05T12:00:00.000000Z", "event": "document.converted", "path": "/tmp/report.pdf", "pages": 42}
{"level": "warning", "logger": "myapp.tasks", "timestamp": "2024-01-05T12:00:00.001000Z", "event": "chunk.empty", "doc_id": "abc123"}
```

Exceptions are serialised as structured dicts (via `structlog.processors.dict_tracebacks`) instead of multi-line stack trace strings, keeping every log entry on a single line.

## FastAPI lifespan example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from logger import configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield

app = FastAPI(lifespan=lifespan)
```

## Per-request context in async code

Use `structlog.contextvars` to attach fields (e.g. a request ID) to every log line emitted during a request, without passing them manually to each call.  The context is stored in a `contextvars.ContextVar` so concurrent async tasks are fully isolated.

```python
import structlog
from fastapi import Request

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request.headers.get("X-Request-ID", "-"),
        method=request.method,
        path=request.url.path,
    )
    return await call_next(request)
```

Every `log.info(...)` call within that request will automatically include `request_id`, `method`, and `path` without any extra arguments.

## Cloud provider integrations

The core package is provider-agnostic: JSON on stdout in production, coloured console in development. That alone is enough for AWS (CloudWatch Logs), GCP (Cloud Logging) and Azure (Log Analytics) to ingest your logs, since all three scrape stdout from containers and serverless runtimes without requiring an SDK. The `logger.integrations` submodules are thin, opt-in helpers for the parts plain stdout JSON doesn't cover — nothing in them is imported by `logger` itself unless you ask for it.

### GCP

Cloud Logging special-cases the `severity`, `message` and `time` keys in a JSON payload (see [structured logging docs](https://cloud.google.com/logging/docs/structured-logging#special-payload-fields)); without them your log level won't drive severity-based filtering/alerting in the Cloud Logging console. Set `LOG_PROVIDER=gcp` (or `configure_logging(provider="gcp")`) to rename fields automatically — no extra dependency required:

```python
from logger import configure_logging

configure_logging(provider="gcp")  # or: LOG_PROVIDER=gcp
```

To correlate log lines with a Cloud Trace span, bind the trace per request:

```python
from logger.integrations.gcp import bind_trace

bind_trace(project_id="my-project", trace_id=trace_id_from_header, span_id=span_id)
```

### AWS

CloudWatch Logs Insights indexes arbitrary top-level JSON keys automatically, so the default output needs no field renaming. `logger.integrations.aws` only adds X-Ray trace correlation — no extra dependency required:

```python
from logger.integrations.aws import bind_xray_trace_from_env

bind_xray_trace_from_env()  # reads _X_AMZN_TRACE_ID, set automatically in Lambda
```

### Azure

Unlike AWS/GCP, scraping stdout on Container Apps/App Service/AKS alone lands logs as an opaque text blob — it does not populate Application Insights' `traces`/`exceptions` tables or Live Metrics. That needs an in-process OpenTelemetry exporter, so this integration pulls in the optional `azure-monitor-opentelemetry` dependency:

```bash
pip install 'logger[azure]'
```

```python
from logger import configure_logging
from logger.integrations.azure import configure_azure_monitor

configure_logging()
configure_azure_monitor()  # reads APPLICATIONINSIGHTS_CONNECTION_STRING, or pass connection_string=
```

This attaches an Application Insights handler *alongside* the existing stdout handler — you keep console/CloudWatch-style output and get App Insights ingestion.