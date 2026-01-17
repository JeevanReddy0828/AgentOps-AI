"""
AgentOps AI - FastAPI Application

Main entry point for the IT Operations AI platform.
Provides REST API endpoints for ticket management, chat interface,
and analytics dashboard.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr

from src.workflows.orchestrator import AgentOrchestrator, WorkflowResult, WorkflowStatus
from src.agents.triage_agent import TriageAgent, TriageResult
from src.rag.knowledge_base import KnowledgeBase, ContextRetriever
from src.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus
from src.api.middleware.auth import get_current_user, User
from src.api.middleware.security import RateLimiter
from src.utils.observability import setup_tracing, MetricsCollector


logger = structlog.get_logger(__name__)

# Global instances (initialized on startup)
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
    retriever = ContextRetriever(knowledge_base=knowledge_base)
    orchestrator = AgentOrchestrator()
    metrics = MetricsCollector(agent_name="api")
    
    # Setup observability
    setup_tracing(service_name="agentops-ai")
    
    logger.info("application_started")
    
    yield
    
    # Cleanup
    logger.info("application_shutting_down")


# Create FastAPI app
app = FastAPI(
    title="AgentOps AI",
    description="Intelligent IT Operations Platform with Agentic AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class TicketCreateRequest(BaseModel):
    """Request to create a new ticket."""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    user_email: Optional[EmailStr] = None
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    attachments: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Cannot connect to VPN",
                "description": "Getting timeout errors when connecting to corporate VPN from home office",
                "user_email": "john.doe@company.com"
            }
        }


class TicketResponse(BaseModel):
    """Response for ticket operations."""
    ticket_id: str
    status: TicketStatus
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    created_at: datetime
    updated_at: datetime
    resolution_summary: Optional[str] = None


class ResolutionRequest(BaseModel):
    """Request to trigger autonomous resolution."""
    max_iterations: int = Field(default=5, ge=1, le=10)
    require_approval: bool = False
    notify_user: bool = True


class ResolutionResponse(BaseModel):
    """Response from resolution attempt."""
    ticket_id: str
    status: WorkflowStatus
    success: bool
    resolution_summary: str
    actions_taken: List[str]
    duration_seconds: float
    escalated: bool = False
    escalation_reason: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message from user."""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Response from chat AI assistant."""
    conversation_id: str
    response: str
    suggested_actions: List[str] = []
    ticket_created: Optional[str] = None
    sources: List[Dict[str, str]] = []


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard data."""
    total_tickets_today: int
    auto_resolved_count: int
    automation_rate: float
    avg_resolution_time_minutes: float
    escalation_rate: float
    top_categories: List[Dict[str, Any]]
    agent_performance: Dict[str, Any]


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness check for Kubernetes."""
    checks = {
        "orchestrator": orchestrator is not None,
        "knowledge_base": knowledge_base is not None
    }
    
    all_ready = all(checks.values())
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"ready": all_ready, "checks": checks}
    )


# ============================================================================
# Ticket Endpoints
# ============================================================================

@app.post("/api/v1/tickets", response_model=TicketResponse, tags=["Tickets"])
async def create_ticket(
    request: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    # current_user: User = Depends(get_current_user)
):
    """
    Create a new IT support ticket.
    
    Optionally triggers automatic triage and resolution.
    """
    import uuid
    ticket_id = f"INC{uuid.uuid4().hex[:8].upper()}"
    
    logger.info("ticket_created", ticket_id=ticket_id, title=request.title)
    
    # Queue for automatic processing
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
        status=TicketStatus.NEW,
        category=request.category,
        priority=request.priority,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse, tags=["Tickets"])
async def get_ticket(ticket_id: str):
    """Get ticket details by ID."""
    # In production, fetch from database
    
    # Check workflow status
    if orchestrator:
        workflow_state = await orchestrator.get_workflow_status(ticket_id)
        if workflow_state:
            return TicketResponse(
                ticket_id=ticket_id,
                status=TicketStatus(workflow_state.get("status", "new")),
                category=TicketCategory(workflow_state.get("ticket_category", "other")) if workflow_state.get("ticket_category") else None,
                priority=TicketPriority(workflow_state.get("ticket_priority", "medium")) if workflow_state.get("ticket_priority") else None,
                created_at=datetime.fromisoformat(workflow_state.get("start_time", datetime.utcnow().isoformat())),
                updated_at=datetime.utcnow(),
                resolution_summary=workflow_state.get("resolution_result", {}).get("resolution_summary")
            )
    
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")


@app.post("/api/v1/tickets/{ticket_id}/resolve", response_model=ResolutionResponse, tags=["Tickets"])
async def resolve_ticket(
    ticket_id: str,
    request: ResolutionRequest
):
    """
    Trigger autonomous resolution for a ticket.
    
    The AI agent will attempt to resolve the ticket using available tools
    and knowledge base context.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    # Get ticket details (would fetch from DB in production)
    workflow_state = await orchestrator.get_workflow_status(ticket_id)
    if not workflow_state:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    
    logger.info("resolution_triggered", ticket_id=ticket_id)
    
    # Run resolution workflow
    result = await orchestrator.run(
        ticket_id=ticket_id,
        title=workflow_state.get("ticket_title", ""),
        description=workflow_state.get("ticket_description", ""),
        user_email=workflow_state.get("user_email"),
        category=TicketCategory(workflow_state.get("ticket_category")) if workflow_state.get("ticket_category") else None,
        priority=TicketPriority(workflow_state.get("ticket_priority")) if workflow_state.get("ticket_priority") else None
    )
    
    return ResolutionResponse(
        ticket_id=ticket_id,
        status=result.status,
        success=result.status == WorkflowStatus.COMPLETED,
        resolution_summary=result.resolution_summary,
        actions_taken=result.actions_taken,
        duration_seconds=result.total_duration_seconds,
        escalated=result.escalated,
        escalation_reason=result.escalation_reason
    )


@app.get("/api/v1/tickets/{ticket_id}/status", tags=["Tickets"])
async def get_resolution_status(ticket_id: str):
    """Get current resolution status for a ticket."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    workflow_state = await orchestrator.get_workflow_status(ticket_id)
    if not workflow_state:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    
    return {
        "ticket_id": ticket_id,
        "status": workflow_state.get("status"),
        "current_agent": workflow_state.get("current_agent"),
        "iteration": workflow_state.get("iteration_count"),
        "actions_taken": workflow_state.get("actions_taken", []),
        "messages": workflow_state.get("messages", [])[-5:]  # Last 5 messages
    }


# ============================================================================
# Chat Endpoints
# ============================================================================

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    message: ChatMessage,
    background_tasks: BackgroundTasks
):
    """
    Send a message to the AI IT support assistant.
    
    The assistant can:
    - Answer IT-related questions
    - Create tickets on behalf of users
    - Provide troubleshooting guidance
    - Check ticket status
    """
    import uuid
    
    conversation_id = message.conversation_id or str(uuid.uuid4())
    
    # Retrieve relevant context
    context_docs = []
    if knowledge_base:
        retriever = ContextRetriever(knowledge_base=knowledge_base)
        context_docs = await retriever.retrieve(
            query=message.message,
            top_k=3
        )
    
    # Generate response using triage agent's LLM
    triage_agent = TriageAgent()
    
    # Simple prompt for chat response
    prompt = f"""You are a helpful IT support assistant. Answer the user's question based on the available context.

User Question: {message.message}

Relevant Knowledge:
{chr(10).join([doc['content'][:500] for doc in context_docs]) if context_docs else 'No specific documentation found.'}

Provide a helpful, concise response. If the user is reporting an issue, ask if they'd like to create a support ticket."""

    from src.agents.base_agent import AgentContext
    response_text = await triage_agent.think(
        prompt=prompt,
        context=AgentContext(conversation_id=conversation_id)
    )
    
    # Extract suggested actions
    suggested_actions = []
    if "ticket" in message.message.lower() or "help" in message.message.lower():
        suggested_actions.append("Create a support ticket")
    if "status" in message.message.lower():
        suggested_actions.append("Check ticket status")
    
    return ChatResponse(
        conversation_id=conversation_id,
        response=response_text,
        suggested_actions=suggested_actions,
        sources=[{"title": doc.get("metadata", {}).get("title", "Unknown"), 
                  "source": doc.get("metadata", {}).get("source", "")} 
                 for doc in context_docs]
    )


@app.get("/api/v1/chat/history/{conversation_id}", tags=["Chat"])
async def get_chat_history(conversation_id: str):
    """Get conversation history for a chat session."""
    # In production, fetch from database
    return {
        "conversation_id": conversation_id,
        "messages": []  # Would return stored messages
    }


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/api/v1/analytics/dashboard", response_model=AnalyticsDashboard, tags=["Analytics"])
async def get_dashboard():
    """Get analytics dashboard data."""
    # In production, aggregate from metrics store
    return AnalyticsDashboard(
        total_tickets_today=45,
        auto_resolved_count=32,
        automation_rate=0.71,
        avg_resolution_time_minutes=8.5,
        escalation_rate=0.15,
        top_categories=[
            {"category": "access", "count": 18},
            {"category": "network", "count": 12},
            {"category": "software", "count": 8},
            {"category": "email", "count": 4},
            {"category": "hardware", "count": 3}
        ],
        agent_performance={
            "triage_agent": {"processed": 45, "accuracy": 0.94},
            "resolution_agent": {"resolved": 32, "success_rate": 0.89},
            "escalation_agent": {"escalated": 7}
        }
    )


@app.get("/api/v1/analytics/trends", tags=["Analytics"])
async def get_trends(days: int = 7):
    """Get ticket resolution trends over time."""
    # In production, aggregate from time-series database
    return {
        "period_days": days,
        "daily_metrics": [
            {"date": "2024-01-15", "tickets": 42, "auto_resolved": 30, "mttr_minutes": 9.2},
            {"date": "2024-01-16", "tickets": 45, "auto_resolved": 32, "mttr_minutes": 8.5}
        ]
    }


@app.get("/api/v1/analytics/agents", tags=["Analytics"])
async def get_agent_metrics():
    """Get detailed agent performance metrics."""
    return {
        "agents": {
            "triage_agent": {
                "total_processed": 450,
                "avg_latency_ms": 245,
                "accuracy": 0.94,
                "category_distribution": {
                    "access": 180,
                    "network": 120,
                    "software": 85,
                    "email": 40,
                    "hardware": 25
                }
            },
            "resolution_agent": {
                "total_attempts": 380,
                "successful": 340,
                "success_rate": 0.89,
                "avg_steps": 2.3,
                "avg_duration_seconds": 12.5,
                "tools_used": {
                    "unlock_account": 95,
                    "reset_password": 82,
                    "push_vpn_config": 45,
                    "install_software": 28
                }
            }
        }
    }


# ============================================================================
# Knowledge Base Endpoints
# ============================================================================

@app.get("/api/v1/knowledge/search", tags=["Knowledge"])
async def search_knowledge(
    query: str,
    doc_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 5
):
    """Search the IT knowledge base."""
    if not knowledge_base:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")
    
    retriever = ContextRetriever(knowledge_base=knowledge_base)
    
    filters = {}
    if category:
        filters["category"] = category
    
    results = await retriever.retrieve(
        query=query,
        doc_type=doc_type,
        filters=filters if filters else None,
        top_k=limit
    )
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@app.get("/api/v1/knowledge/stats", tags=["Knowledge"])
async def get_knowledge_stats():
    """Get knowledge base statistics."""
    if not knowledge_base:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")
    
    return knowledge_base.get_stats()


# ============================================================================
# Background Tasks
# ============================================================================

async def process_ticket_async(
    ticket_id: str,
    title: str,
    description: str,
    user_email: Optional[str],
    category: Optional[TicketCategory],
    priority: Optional[TicketPriority]
):
    """Background task to process ticket through orchestrator."""
    if not orchestrator:
        logger.error("orchestrator_not_available")
        return
    
    try:
        result = await orchestrator.run(
            ticket_id=ticket_id,
            title=title,
            description=description,
            user_email=user_email,
            category=category,
            priority=priority
        )
        
        logger.info(
            "ticket_processed",
            ticket_id=ticket_id,
            status=result.status.value,
            duration=result.total_duration_seconds
        )
        
    except Exception as e:
        logger.error("ticket_processing_failed", ticket_id=ticket_id, error=str(e))


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
