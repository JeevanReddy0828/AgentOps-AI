"""
AgentOps AI - FastAPI Application

Main API entry point for the agentic IT operations platform.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import uuid
import os
import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr

from src.workflows.orchestrator import AgentOrchestrator, WorkflowResult, WorkflowStatus
from src.rag.knowledge_base import KnowledgeBase, ContextRetriever
from src.models.ticket import TicketStatus, TicketCategory, TicketPriority
from src.utils.observability import setup_tracing, MetricsCollector

# Import Anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


logger = structlog.get_logger(__name__)

# Global instances
orchestrator: Optional[AgentOrchestrator] = None
knowledge_base: Optional[KnowledgeBase] = None
metrics: Optional[MetricsCollector] = None
anthropic_client: Optional[Any] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global orchestrator, knowledge_base, metrics, anthropic_client
    
    logger.info("application_starting")
    
    # Initialize components
    knowledge_base = KnowledgeBase()
    orchestrator = AgentOrchestrator()
    metrics = MetricsCollector(agent_name="api")
    
    # Initialize Anthropic client
    if ANTHROPIC_AVAILABLE:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            anthropic_client = anthropic.Anthropic(api_key=api_key)
            logger.info("anthropic_client_initialized")
        else:
            logger.warning("anthropic_api_key_not_set")
    
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
    ticket_created: Optional[str] = None


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
        "knowledge_base": knowledge_base is not None,
        "anthropic": anthropic_client is not None
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

# Store conversation history in memory (use Redis in production)
conversation_history: Dict[str, List[Dict[str, str]]] = {}

# Store context for ticket creation
chat_context: Dict[str, Dict[str, Any]] = {}


def extract_issue_from_history(history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Extract issue details from conversation history."""
    user_messages = [msg["content"] for msg in history if msg["role"] == "user"]
    full_conversation = "\n".join(user_messages)
    full_conversation_lower = full_conversation.lower()
    
    # Determine category
    if any(word in full_conversation_lower for word in ["password", "login", "locked", "access", "authentication"]):
        category = "access"
        title = "Password/Login Issue"
    elif any(word in full_conversation_lower for word in ["vpn", "network", "wifi", "internet", "connect", "connection"]):
        category = "network"
        title = "Network/VPN Connectivity Issue"
    elif any(word in full_conversation_lower for word in ["email", "outlook", "mail", "calendar"]):
        category = "email"
        title = "Email/Outlook Issue"
    elif any(word in full_conversation_lower for word in ["install", "software", "application", "app", "update"]):
        category = "software"
        title = "Software Installation/Issue"
    elif any(word in full_conversation_lower for word in ["computer", "laptop", "hardware", "printer", "monitor", "keyboard", "mouse"]):
        category = "hardware"
        title = "Hardware Issue"
    else:
        category = "other"
        title = "IT Support Request"
    
    # Determine priority based on urgency words
    if any(word in full_conversation_lower for word in ["urgent", "asap", "critical", "emergency", "immediately", "can't work"]):
        priority = "high"
    elif any(word in full_conversation_lower for word in ["important", "soon", "need"]):
        priority = "medium"
    else:
        priority = "low"
    
    return {
        "title": title,
        "description": full_conversation,
        "category": category,
        "priority": priority
    }


def should_create_ticket(message: str, history: List[Dict[str, str]]) -> bool:
    """Determine if user wants to create a ticket based on message and context."""
    message_lower = message.lower()
    
    # Explicit ticket creation phrases
    explicit_phrases = [
        "create a ticket", "create ticket", "submit ticket", "open ticket",
        "make a ticket", "need ticket", "want ticket", "yes create", "yes please create",
        "please create", "create one", "make one", "open one", "submit one",
        "need it support", "need help from it", "escalate", "talk to human",
        "yes do it", "go ahead and create", "yes, create", "yep create",
        "just create", "can you create", "please make", "i need a ticket"
    ]
    
    if any(phrase in message_lower for phrase in explicit_phrases):
        return True
    
    # Check if user is confirming after being asked about ticket creation
    confirmation_phrases = ["yes", "yep", "yeah", "sure", "ok", "okay", "please", "do it", "go ahead"]
    
    if any(phrase in message_lower for phrase in confirmation_phrases):
        # Check if the last assistant message mentioned ticket creation
        for msg in reversed(history):
            if msg["role"] == "assistant":
                assistant_msg_lower = msg["content"].lower()
                if any(phrase in assistant_msg_lower for phrase in ["create a ticket", "create a support ticket", "open a ticket", "submit a ticket"]):
                    return True
                break
    
    return False


@app.post("/api/v1/chat")
async def chat_with_assistant(request: ChatMessage, background_tasks: BackgroundTasks):
    """Chat with the AI IT support assistant powered by Claude."""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    ticket_created = None
    
    # Get or create conversation history
    if conversation_id not in conversation_history:
        conversation_history[conversation_id] = []
    
    history = conversation_history[conversation_id]
    
    # Add user message to history
    history.append({"role": "user", "content": request.message})
    
    # Check if user wants to create a ticket - do this BEFORE calling Claude
    if should_create_ticket(request.message, history) and len(history) >= 2:
        # Extract issue details from conversation
        issue_info = extract_issue_from_history(history)
        
        # Create the ticket
        ticket_id = f"INC{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.utcnow().isoformat()
        
        ticket_data = {
            "ticket_id": ticket_id,
            "title": issue_info["title"],
            "description": issue_info["description"],
            "user_email": None,
            "category": issue_info["category"],
            "priority": issue_info["priority"],
            "created_at": created_at,
            "status": "new"
        }
        
        orchestrator.store_ticket(ticket_id, ticket_data)
        ticket_created = ticket_id
        
        # Start async processing
        category_enum = None
        if issue_info["category"] in ["network", "hardware", "software", "access", "email", "other"]:
            category_enum = TicketCategory(issue_info["category"])
        
        background_tasks.add_task(
            process_ticket_async,
            ticket_id=ticket_id,
            title=issue_info["title"],
            description=issue_info["description"],
            user_email=None,
            category=category_enum,
            priority=None
        )
        
        logger.info("ticket_created_from_chat", ticket_id=ticket_id, conversation_id=conversation_id)
        
        response_text = f"""I've created support ticket **{ticket_id}** for you with the following details:

**Issue:** {issue_info['title']}
**Category:** {issue_info['category'].title()}
**Priority:** {issue_info['priority'].title()}

Our IT team will review your ticket and get back to you soon. You can track its progress in the Tickets tab.

Is there anything else I can help you with?"""
        
        # Add assistant response to history
        history.append({"role": "assistant", "content": response_text})
        
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "suggested_actions": ["Check ticket status", "Ask another question"],
            "ticket_created": ticket_id
        }
    
    # Build suggested actions based on message content
    suggested_actions = []
    message_lower = request.message.lower()
    
    if any(word in message_lower for word in ["ticket", "create", "submit", "report"]):
        suggested_actions.append("Create a ticket")
    if any(word in message_lower for word in ["password", "reset", "forgot", "locked"]):
        suggested_actions.append("Reset password")
    if any(word in message_lower for word in ["vpn", "connect", "network", "wifi"]):
        suggested_actions.append("Check VPN status")
    if any(word in message_lower for word in ["search", "find", "how", "help"]):
        suggested_actions.append("Search knowledge base")
    
    # If no specific actions detected, add defaults
    if not suggested_actions:
        suggested_actions = ["Create a ticket", "Search knowledge base"]
    
    try:
        # Check if Anthropic client is available
        if anthropic_client is None:
            logger.warning("anthropic_client_not_available")
            response_text = generate_fallback_response(request.message)
        else:
            # Call Claude API with tool use for ticket creation
            system_prompt = """You are a helpful IT support assistant. Your role is to:

1. Help users troubleshoot IT issues (VPN, passwords, software, hardware, network)
2. Guide them through common solutions step by step
3. Create support tickets when needed

IMPORTANT RULES:
- Be concise (2-4 sentences unless detailed instructions are needed)
- If the user has already tried basic troubleshooting and it didn't work, IMMEDIATELY offer to create a ticket
- Don't keep asking for more information if they've clearly explained the problem
- When the user says "create a ticket", "yes create one", or confirms they want a ticket, acknowledge it directly

For VPN issues specifically:
- If user has tried: restarting, reconnecting, different servers, different clients - that's enough troubleshooting
- Offer to create ticket immediately

Example good response when user has tried everything:
"I can see you've already tried the standard troubleshooting steps without success. Let me create a support ticket for our IT team to investigate this further. Just say 'create a ticket' to confirm."

Example bad response (don't do this):
"Let me ask a few more questions..." (when they've already provided details)"""

            # Build messages for Claude
            messages = []
            for msg in history[-10:]:  # Keep last 10 messages for context
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Call Claude
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system=system_prompt,
                messages=messages
            )
            
            response_text = response.content[0].text
            logger.info("chat_response_generated", conversation_id=conversation_id)
        
        # Add assistant response to history
        history.append({"role": "assistant", "content": response_text})
        
        # Keep history manageable
        if len(history) > 20:
            conversation_history[conversation_id] = history[-20:]
        
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "suggested_actions": suggested_actions,
            "ticket_created": ticket_created
        }
        
    except Exception as e:
        logger.error("chat_error", error=str(e), conversation_id=conversation_id)
        
        # Fallback response
        fallback = generate_fallback_response(request.message)
        history.append({"role": "assistant", "content": fallback})
        
        return {
            "response": fallback,
            "conversation_id": conversation_id,
            "suggested_actions": ["Create a ticket", "Contact IT support"],
            "ticket_created": None
        }


def generate_fallback_response(message: str) -> str:
    """Generate a helpful fallback response when Claude is unavailable."""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["hi", "hello", "hey"]):
        return "Hello! I'm the IT Support Assistant. How can I help you today? I can assist with password resets, VPN issues, software problems, and more."
    
    if any(word in message_lower for word in ["password", "reset", "forgot"]):
        return "For password issues, please try the self-service password reset portal at password.company.com. If that doesn't work, I can create a ticket for the IT team to assist you. Would you like me to do that?"
    
    if any(word in message_lower for word in ["vpn", "connect"]):
        return "For VPN issues, try these steps: 1) Restart the VPN client, 2) Check your internet connection, 3) Try a different network. If the issue persists, I can create a support ticket for you."
    
    if any(word in message_lower for word in ["slow", "performance"]):
        return "For performance issues, try: 1) Restart your computer, 2) Close unnecessary applications, 3) Check for Windows updates. If problems continue, please create a ticket with details about when the slowness occurs."
    
    if any(word in message_lower for word in ["email", "outlook"]):
        return "For email issues, try: 1) Restart Outlook, 2) Check your internet connection, 3) Clear Outlook cache. If you're still having trouble, I can help create a support ticket."
    
    if any(word in message_lower for word in ["install", "software", "application"]):
        return "For software installations, please check the Company Software Center first. If the software isn't available there, create a ticket specifying the software name and business justification."
    
    return "I'd be happy to help with your IT issue. Could you provide more details about what's happening? You can also create a support ticket in the Tickets tab for our IT team to investigate."


# ============== Analytics Endpoints ==============

@app.get("/api/v1/analytics/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard():
    """Get analytics dashboard data."""
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
    try:
        retriever = ContextRetriever(knowledge_base=knowledge_base)
        results = await retriever.retrieve(query=query, top_k=limit)
        
        return {
            "query": query,
            "results": [
                {
                    "content": r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", ""),
                    "source": r.get("metadata", {}).get("source", "Unknown")
                }
                for r in results
            ] if results else []
        }
    except Exception as e:
        logger.error("knowledge_search_error", error=str(e))
        return {"query": query, "results": []}


@app.get("/api/v1/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics."""
    try:
        return knowledge_base.get_stats()
    except Exception as e:
        return {"error": str(e), "documents": 0}


# ============== Metrics Endpoint ==============

@app.get("/metrics")
async def get_prometheus_metrics():
    """Prometheus metrics endpoint."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response
        
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except ImportError:
        return {"error": "prometheus_client not installed"}