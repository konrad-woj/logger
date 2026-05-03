# Structured logger

Thin wrapper around [structlog](https://www.structlog.org/) that gives coloured console output in development and machine-readable JSON in production.

## Environment variables

| Variable    | Values                              | Default  |
|-------------|-------------------------------------|----------|
| `LOG_ENV`   | `production` → JSON, anything else → console | dev console |
| `LOG_LEVEL` | stdlib level name (`DEBUG`, `INFO`, `WARNING`, …) | `INFO` |

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
2024-11-05T12:00:00.000000Z [info     ] document.converted  [document_processor.conversion] pages=42 path=/tmp/report.pdf
2024-11-05T12:00:00.001000Z [warning  ] chunk.empty         [document_processor.chunking] doc_id=abc123
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
{"level": "info", "logger": "document_processor.conversion", "timestamp": "2024-11-05T12:00:00.000000Z", "event": "document.converted", "path": "/tmp/report.pdf", "pages": 42}
{"level": "warning", "logger": "document_processor.chunking", "timestamp": "2024-11-05T12:00:00.001000Z", "event": "chunk.empty", "doc_id": "abc123"}
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