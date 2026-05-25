"""
Observability setup for patchmon-mcp.

Structured logging is always on. InfluxDB, OTEL, and NATS are opt-in via env vars.
"""

import logging
import os
import sys
import time
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_file:
        handler: logging.Handler = logging.FileHandler(log_file)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    handler.setFormatter(formatter)


# ---------------------------------------------------------------------------
# InfluxDB telemetry (opt-in)
# ---------------------------------------------------------------------------

_influx_client = None
_influx_write_api = None
_influx_bucket = None


def _get_influx():
    global _influx_client, _influx_write_api, _influx_bucket
    url = os.getenv("INFLUXDB_URL")
    if not url:
        return None, None
    if _influx_client is not None:
        return _influx_write_api, _influx_bucket
    try:
        from influxdb_client_3 import InfluxDBClient3  # type: ignore

        token = os.environ["INFLUXDB_TOKEN"]
        _influx_bucket = os.getenv("INFLUXDB_BUCKET", "patchmon-mcp")
        _influx_client = InfluxDBClient3(host=url, token=token, database=_influx_bucket)
        _influx_write_api = _influx_client
        return _influx_write_api, _influx_bucket
    except Exception:
        structlog.get_logger().warning("influxdb_init_failed", exc_info=True)
        return None, None


# ---------------------------------------------------------------------------
# OTEL tracing (opt-in)
# ---------------------------------------------------------------------------

_tracer = None


def get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return None
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

        resource = Resource.create({"service.name": "patchmon-mcp"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("patchmon-mcp")
    except Exception:
        structlog.get_logger().warning("otel_init_failed", exc_info=True)
    return _tracer


# ---------------------------------------------------------------------------
# NATS publishing (opt-in)
# ---------------------------------------------------------------------------

_nats_client = None
_nats_subject_prefix = None


async def _get_nats():
    global _nats_client, _nats_subject_prefix
    url = os.getenv("NATS_URL")
    if not url:
        return None, None
    if _nats_client is not None:
        return _nats_client, _nats_subject_prefix
    try:
        import nats  # type: ignore

        _nats_client = await nats.connect(url)
        _nats_subject_prefix = os.getenv("NATS_SUBJECT_PREFIX", "patchmon")
        return _nats_client, _nats_subject_prefix
    except Exception:
        structlog.get_logger().warning("nats_init_failed", exc_info=True)
        return None, None


# ---------------------------------------------------------------------------
# Unified metric emission
# ---------------------------------------------------------------------------

async def emit_metric(
    measurement: str,
    tags: dict[str, str],
    fields: dict[str, Any],
) -> None:
    """Write a data point to InfluxDB and/or publish to NATS (both opt-in)."""
    write_api, bucket = _get_influx()
    if write_api is not None:
        try:
            from influxdb_client_3 import Point  # type: ignore

            point = Point(measurement)
            for k, v in tags.items():
                point.tag(k, v)
            for k, v in fields.items():
                if v is not None:
                    point.field(k, v)
            point.time(int(time.time() * 1e9))
            write_api.write(record=point)
        except Exception:
            structlog.get_logger().warning("influxdb_write_failed", exc_info=True)

    nc, prefix = await _get_nats()
    if nc is not None:
        try:
            import json

            subject = f"{prefix}.{measurement}"
            payload = json.dumps({"tags": tags, "fields": fields}).encode()
            await nc.publish(subject, payload)
        except Exception:
            structlog.get_logger().warning("nats_publish_failed", exc_info=True)


configure_logging()
