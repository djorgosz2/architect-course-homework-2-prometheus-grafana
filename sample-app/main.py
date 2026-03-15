"""Sample FastAPI backend with OpenTelemetry metrics instrumentation.

Exposes standard HTTP metrics + custom application metrics on :9464/metrics.
Simulates realistic traffic patterns with variable latency and error rates.
"""

import random
import time

from fastapi import FastAPI, HTTPException
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from prometheus_client import start_http_server

resource = Resource.create({"service.name": "myapp-backend", "service.namespace": "myapp"})
reader = PrometheusMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("myapp", version="1.0.0")

# Custom application metrics (analogous to real-world tool call / DB pool / operation metrics)
request_processing_duration = meter.create_histogram(
    name="myapp.request_processing.duration",
    description="Duration of business logic processing in seconds",
    unit="s",
)
operation_counter = meter.create_counter(
    name="myapp.operations.total",
    description="Total number of business operations",
    unit="{operation}",
)
db_connections_active = meter.create_up_down_counter(
    name="myapp.db.connections.active",
    description="Number of active database connections",
    unit="{connection}",
)
external_api_duration = meter.create_histogram(
    name="myapp.external_api.duration",
    description="Duration of external API calls in seconds",
    unit="s",
)

app = FastAPI(title="MyApp Backend")
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/items")
async def list_items():
    start = time.time()
    # Simulate DB query
    db_connections_active.add(1)
    delay = random.uniform(0.01, 0.15)
    time.sleep(delay)
    db_connections_active.add(-1)

    request_processing_duration.record(time.time() - start, {"endpoint": "list_items", "status": "success"})
    operation_counter.add(1, {"operation": "list_items", "status": "success"})
    return {"items": [{"id": i, "name": f"Item {i}"} for i in range(10)]}


@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    start = time.time()
    db_connections_active.add(1)
    time.sleep(random.uniform(0.005, 0.08))
    db_connections_active.add(-1)

    # Simulate occasional 404
    if item_id > 100:
        operation_counter.add(1, {"operation": "get_item", "status": "error"})
        request_processing_duration.record(time.time() - start, {"endpoint": "get_item", "status": "error"})
        raise HTTPException(status_code=404, detail="Item not found")

    request_processing_duration.record(time.time() - start, {"endpoint": "get_item", "status": "success"})
    operation_counter.add(1, {"operation": "get_item", "status": "success"})
    return {"id": item_id, "name": f"Item {item_id}"}


@app.post("/api/process")
async def process_data():
    """Simulate a heavier processing endpoint (like document processing / AI calls)."""
    start = time.time()

    # Simulate external API call
    api_start = time.time()
    delay = random.uniform(0.1, 2.0)
    time.sleep(delay)
    external_api_duration.record(time.time() - api_start, {"service": "external-ai", "status": "success"})

    # Simulate occasional 5xx
    if random.random() < 0.05:
        operation_counter.add(1, {"operation": "process_data", "status": "error"})
        request_processing_duration.record(time.time() - start, {"endpoint": "process_data", "status": "error"})
        raise HTTPException(status_code=500, detail="Processing failed")

    request_processing_duration.record(time.time() - start, {"endpoint": "process_data", "status": "success"})
    operation_counter.add(1, {"operation": "process_data", "status": "success"})
    return {"status": "processed"}


# Start Prometheus metrics server on port 9464 (same convention as real setup)
start_http_server(port=9464, addr="0.0.0.0")
