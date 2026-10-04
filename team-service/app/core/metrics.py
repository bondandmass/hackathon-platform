"""Prometheus metrics for every request."""
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled", ["service", "method", "route", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
IN_PROGRESS = Gauge("http_requests_in_progress", "HTTP requests in progress", ["service"])


def install_metrics(app: FastAPI, service: str) -> None:
    @app.middleware("http")
    async def record(request: Request, call_next):
        IN_PROGRESS.labels(service).inc()
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            # Use the route template (/teams/{team_id}), never the raw path, to keep label counts small.
            route_label = getattr(route, "path", "unmatched")
            LATENCY.labels(service, request.method, route_label).observe(time.perf_counter() - start)
            REQUESTS.labels(service, request.method, route_label, str(status_code)).inc()
            IN_PROGRESS.labels(service).dec()

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
