"""
AgentOps AI - FastAPI Application

Main API entry point for the agentic IT operations platform.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import uuid
import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr

from src.workflows.orchestrator import AgentOrchestrator, WorkflowResult, WorkflowStatus
from src.rag.knowledge_base import KnowledgeBase, ContextRetriever
from src.models.ticket import TicketStatus, TicketCategory, TicketPriority
from src.utils.observability import setup_tracing, MetricsCollector


logger = structlog.get_logger(__name__)

# Global instances
orchestrator: Optional[AgentOrchestrator] = None
knowledge_base: Optional[KnowledgeBase] = None
metrics: Optional[MetricsCollector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global orchestrator, knowledge_base, metrics
    
    logger.info("application_starting")
    
    # Initialize components
    knowledge_base = KnowledgeBase()
    orchestrator = AgentOrchestrator()
    metrics = MetricsCollector(agent_name="api")
    
    # Setup tracing
    setup_tracing(service_name="agentops-ai")
    
    logger.info("application_started")
    
    yield
    
    logger.info("application_shutting_down")


app = FastAPI(
    title="AgentOps AI",
    description="Intelligent IT Operations Platform with Multi-Agent Orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Request/Response Models ==============

class TicketCreateRequest(BaseModel):
    """Request to create a new ticket."""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    user_email: Optional[EmailStr] = None
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Cannot connect to VPN",
                "description": "Getting timeout errors when connecting to corporate VPN from home office",
                "user_email": "john.doe@company.com"
            }
        }
    }


class TicketResponse(BaseModel):
    """Response for ticket operations."""
    ticket_id: str
    title: str
    description: str
    status: str
    category: Optional[str] = None
    priority: Optional[str] = None
    created_at: str
    user_email: Optional[str] = None


class ResolutionStatusResponse(BaseModel):
    """Response for resolution status."""
    ticket_id: str
    status: str
    resolution_summary: Optional[str] = None
    actions_taken: List[str] = []
    escalated: bool = False
    escalation_reason: Optional[str] = None
    completed: bool = False


class ChatMessage(BaseModel):
    """Chat message from user."""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from AI assistant."""
    response: str
    conversation_id: str
    suggested_actions: List[str] = []


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard data."""
    total_tickets: int
    resolved_tickets: int
    auto_resolved: int
    escalated: int
    avg_resolution_time_minutes: float
    resolution_rate: float
    top_categories: Dict[str, int]


# ============== Health Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {
        "status": "ready",
        "orchestrator": orchestrator is not None,
        "knowledge_base": knowledge_base is not None
    }


# ============== Ticket Endpoints ==============

@app.post("/api/v1/tickets", response_model=TicketResponse)
async def create_ticket(
    request: TicketCreateRequest,
    background_tasks: BackgroundTasks
):
    """Create a new IT support ticket and start processing."""
    ticket_id = f"INC{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.utcnow().isoformat()
    
    # Store ticket
    ticket_data = {
        "ticket_id": ticket_id,
        "title": request.title,
        "description": request.description,
        "user_email": request.user_email,
        "category": request.category.value if request.category else None,
        "priority": request.priority.value if request.priority else None,
        "created_at": created_at,
        "status": "new"
    }
    
    orchestrator.store_ticket(ticket_id, ticket_data)
    
    logger.info("ticket_created", ticket_id=ticket_id, title=request.title)
    
    # Start async processing
    background_tasks.add_task(
        process_ticket_async,
        ticket_id=ticket_id,
        title=request.title,
        description=request.description,
        user_email=request.user_email,
        category=request.category,
        priority=request.priority
    )
    
    return TicketResponse(
        ticket_id=ticket_id,
        title=request.title,
        description=request.description,
        status="new",
        category=request.category.value if request.category else None,
        priority=request.priority.value if request.priority else None,
        created_at=created_at,
        user_email=request.user_email
    )


async def process_ticket_async(
    ticket_id: str,
    title: str,
    description: str,
    user_email: Optional[str],
    category: Optional[TicketCategory],
    priority: Optional[TicketPriority]
):
    """Background task to process ticket through orchestrator."""
    try:
        logger.info("workflow_started", ticket_id=ticket_id)
        
        result = await orchestrator.run(
            ticket_id=ticket_id,
            title=title,
            description=description,
            user_email=user_email,
            category=category,
            priority=priority
        )
        
        logger.info(
            "workflow_completed",
            ticket_id=ticket_id,
            status=result.status.value,
            duration=result.total_duration_seconds
        )
        
    except Exception as e:
        logger.error("ticket_processing_failed", ticket_id=ticket_id, error=str(e))


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    """Get ticket details and current status."""
    try:
        workflow_state = await orchestrator.get_workflow_status(ticket_id)
        
        if workflow_state.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        
        # Map status to valid TicketStatus or use as-is
        raw_status = workflow_state.get("status", "new")
        try:
            status = TicketStatus(raw_status).value
        except ValueError:
            # If not a valid TicketStatus, use the raw value
            status = raw_status
        
        return TicketResponse(
            ticket_id=ticket_id,
            title=workflow_state.get("title", ""),
            description=workflow_state.get("description", ""),
            status=status,
            category=workflow_state.get("category"),
            priority=workflow_state.get("priority"),
            created_at=workflow_state.get("created_at", datetime.utcnow().isoformat()),
            user_email=workflow_state.get("user_email")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("unhandled_exception", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tickets/{ticket_id}/status", response_model=ResolutionStatusResponse)
async def get_resolution_status(ticket_id: str):
    """Get the resolution status of a ticket."""
    try:
        workflow_state = await orchestrator.get_workflow_status(ticket_id)
        
        if workflow_state.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        
        return ResolutionStatusResponse(
            ticket_id=ticket_id,
            status=workflow_state.get("status", "unknown"),
            resolution_summary=workflow_state.get("resolution_summary"),
            actions_taken=workflow_state.get("actions_taken", []),
            escalated=workflow_state.get("escalated", False),
            escalation_reason=workflow_state.get("escalation_reason"),
            completed=workflow_state.get("completed", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("unhandled_exception", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tickets/{ticket_id}/resolve", response_model=ResolutionStatusResponse)
async def trigger_resolution(ticket_id: str, background_tasks: BackgroundTasks):
    """Manually trigger resolution for a ticket."""
    workflow_state = await orchestrator.get_workflow_status(ticket_id)
    
    if workflow_state.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    
    # Re-trigger processing
    background_tasks.add_task(
        process_ticket_async,
        ticket_id=ticket_id,
        title=workflow_state.get("title", ""),
        description=workflow_state.get("description", ""),
        user_email=workflow_state.get("user_email"),
        category=None,
        priority=None
    )
    
    return ResolutionStatusResponse(
        ticket_id=ticket_id,
        status="processing",
        completed=False
    )


# ============== Chat Endpoints ==============

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatMessage):
    """Chat with the AI IT support assistant."""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    try:
        # Get relevant context from knowledge base
        context = await knowledge_base.search(
            query=request.message,
            top_k=3
        )
        
        # For now, return a helpful response
        # In production, this would use the LLM with retrieved context
        response = f"I understand you're asking about: {request.message[:100]}..."
        
        if context:
            response += " I found some relevant information that might help."
        
        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            suggested_actions=["Create a ticket", "Search knowledge base"]
        )
        
    except Exception as e:
        logger.error("chat_error", error=str(e))
        return ChatResponse(
            response="I'm having trouble processing your request. Please try again.",
            conversation_id=conversation_id,
            suggested_actions=["Create a ticket"]
        )


# ============== Analytics Endpoints ==============

@app.get("/api/v1/analytics/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard():
    """Get analytics dashboard data."""
    # Return mock data for demonstration
    return AnalyticsDashboard(
        total_tickets=150,
        resolved_tickets=120,
        auto_resolved=85,
        escalated=15,
        avg_resolution_time_minutes=12.5,
        resolution_rate=0.80,
        top_categories={
            "access": 45,
            "network": 35,
            "software": 30,
            "hardware": 25,
            "email": 15
        }
    )


@app.get("/api/v1/analytics/trends")
async def get_analytics_trends(days: int = 7):
    """Get ticket trends over time."""
    # Return mock trend data
    from datetime import timedelta
    
    trends = []
    base_date = datetime.utcnow()
    
    for i in range(days):
        date = base_date - timedelta(days=i)
        trends.append({
            "date": date.strftime("%Y-%m-%d"),
            "total": 20 + (i * 2) % 10,
            "resolved": 15 + (i * 3) % 8,
            "escalated": 2 + i % 3
        })
    
    return {"trends": trends[::-1]}


@app.get("/api/v1/analytics/agents")
async def get_agent_metrics():
    """Get agent performance metrics."""
    return {
        "agents": [
            {
                "name": "triage_agent",
                "requests_handled": 150,
                "avg_latency_ms": 450,
                "success_rate": 0.95
            },
            {
                "name": "resolution_agent",
                "requests_handled": 120,
                "avg_latency_ms": 2500,
                "success_rate": 0.85
            },
            {
                "name": "compliance_agent",
                "requests_handled": 120,
                "avg_latency_ms": 150,
                "success_rate": 0.99
            }
        ]
    }


# ============== Knowledge Base Endpoints ==============

@app.get("/api/v1/knowledge/search")
async def search_knowledge_base(query: str, limit: int = 5):
    """Search the knowledge base."""
    results = await knowledge_base.search(query=query, top_k=limit)
    
    return {
        "query": query,
        "results": [
            {
                "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                "relevance": r.relevance_score,
                "source": r.metadata.get("source", "Unknown")
            }
            for r in results
        ]
    }


@app.get("/api/v1/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics."""
    return knowledge_base.get_stats()


# ============== Metrics Endpoint ==============

@app.get("/metrics")
async def get_prometheus_metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )