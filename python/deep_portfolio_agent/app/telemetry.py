import os
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

tracer = trace.get_tracer("deep-portfolio-agent")
meter = metrics.get_meter("deep-portfolio-agent")

# Custom metrics
rebalance_counter = meter.create_counter(
    "portfolio_rebalance_total",
    description="Total number of portfolio rebalance executions",
    unit="1"
)
var_95_gauge = meter.create_gauge(
    "portfolio_var_95",
    description="Current portfolio Value at Risk (95% confidence)",
    unit="percent"
)
es_gauge = meter.create_gauge(
    "portfolio_expected_shortfall",
    description="Current portfolio Expected Shortfall (ES)",
    unit="percent"
)

def init_telemetry(service_name: str = "deep-portfolio-agent"):
    resource = Resource(attributes={"service.name": service_name})
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    
    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)
    
    # Metrics
    metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
