"""
Observability Module

Tracing, metrics, and logging utilities for monitoring agent performance.
"""

from typing import Any, Callable, Dict, Optional
from functools import wraps
from datetime import datetime
import structlog
from prometheus_client import Counter, Histogram, Gauge


logger = structlog.get_logger(__name__)


# Prometheus Metrics
AGENT_REQUESTS = Counter(
    "agent_requests_total",
    "Total agent requests",
    ["agent_name", "action"]
)

AGENT_LATENCY = Histogram(
    "agent_latency_seconds",
    "Agent execution latency",
    ["agent_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

ACTIVE_WORKFLOWS = Gauge(
    "active_workflows",
    "Number of active workflows"
)

TOOL_EXECUTIONS = Counter(
    "tool_executions_total",
    "Total tool executions",
    ["tool_name", "success"]
)


def setup_tracing(service_name: str = "agentops-ai"):
    """Initialize OpenTelemetry tracing."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        
        resource = Resource(attributes={"service.name": service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        logger.info("tracing_initialized", service=service_name)
    except ImportError:
        logger.warning("opentelemetry_not_available")


def trace_agent_action(func: Callable) -> Callable:
    """Decorator to trace agent action execution."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = datetime.utcnow()
        agent_name = getattr(args[0], 'name', 'unknown') if args else 'unknown'
        
        try:
            result = await func(*args, **kwargs)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            AGENT_LATENCY.labels(agent_name=agent_name).observe(duration)
            AGENT_REQUESTS.labels(agent_name=agent_name, action=func.__name__).inc()
            
            logger.debug(
                "agent_action_completed",
                agent=agent_name,
                action=func.__name__,
                duration=duration
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "agent_action_failed",
                agent=agent_name,
                action=func.__name__,
                error=str(e)
            )
            raise
    
    return wrapper


class MetricsCollector:
    """Collect and manage metrics for an agent."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.tool_executions: Dict[str, Dict[str, int]] = {}
    
    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        execution_time: Optional[float] = None
    ):
        """Record a tool execution."""
        TOOL_EXECUTIONS.labels(
            tool_name=tool_name,
            success=str(success).lower()
        ).inc()
        
        if tool_name not in self.tool_executions:
            self.tool_executions[tool_name] = {"success": 0, "failure": 0}
        
        key = "success" if success else "failure"
        self.tool_executions[tool_name][key] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collected statistics."""
        return {
            "agent_name": self.agent_name,
            "tool_executions": self.tool_executions
        }
