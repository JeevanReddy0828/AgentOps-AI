"""
Agent Orchestrator Module

LangGraph-based workflow orchestration for multi-agent IT operations.
Implements a state machine that coordinates triage, resolution, escalation,
and compliance agents for end-to-end ticket handling.
"""

from typing import Any, Dict, List, Optional, TypedDict, Annotated, Literal
from datetime import datetime
from enum import Enum
import operator
import structlog
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.triage_agent import TriageAgent, TriageResult, TriageDecision
from src.agents.resolution_agent import ResolutionAgent, ResolutionResult
from src.agents.compliance_agent import ComplianceAgent
from src.models.ticket import Ticket, TicketStatus, TicketCategory, TicketPriority
from src.models.agent_state import AgentState


logger = structlog.get_logger(__name__)


class WorkflowStatus(str, Enum):
    """Status of the orchestration workflow."""
    PENDING = "pending"
    TRIAGING = "triaging"
    RESOLVING = "resolving"
    ESCALATING = "escalating"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class OrchestratorState(TypedDict):
    """State maintained across the workflow graph."""
    # Ticket information
    ticket_id: str
    ticket_title: str
    ticket_description: str
    ticket_category: Optional[str]
    ticket_priority: Optional[str]
    user_email: Optional[str]
    
    # Workflow state
    status: str
    current_agent: Optional[str]
    iteration_count: int
    max_iterations: int
    
    # Agent outputs
    triage_result: Optional[Dict[str, Any]]
    resolution_result: Optional[Dict[str, Any]]
    compliance_result: Optional[Dict[str, Any]]
    
    # Accumulating history
    messages: Annotated[List[Dict[str, Any]], operator.add]
    actions_taken: Annotated[List[str], operator.add]
    
    # Routing decisions
    next_step: Optional[str]
    requires_human: bool
    escalation_reason: Optional[str]
    
    # Metadata
    start_time: str
    end_time: Optional[str]
    total_cost_tokens: int


class WorkflowResult(BaseModel):
    """Final result of the orchestration workflow."""
    ticket_id: str
    status: WorkflowStatus
    resolution_summary: str
    actions_taken: List[str]
    triage_result: Optional[TriageResult] = None
    resolution_result: Optional[ResolutionResult] = None
    escalated: bool = False
    escalation_reason: Optional[str] = None
    total_duration_seconds: float
    iteration_count: int


class AgentOrchestrator:
    """
    LangGraph-based orchestrator for multi-agent IT operations.
    
    Implements a state machine with the following flow:
    
    START → TRIAGE → [Decision]
                      ├─ AUTO_RESOLVE → RESOLVE → VERIFY → END
                      ├─ AGENT_RESOLUTION → RESOLVE → VERIFY → [Success?]
                      │                                         ├─ Yes → END
                      │                                         └─ No → ESCALATE
                      ├─ HUMAN_ESCALATION → ESCALATE → END
                      └─ INFORMATION_REQUEST → REQUEST_INFO → TRIAGE
    """
    
    def __init__(
        self,
        triage_agent: Optional[TriageAgent] = None,
        resolution_agent: Optional[ResolutionAgent] = None,
        compliance_agent: Optional[ComplianceAgent] = None,
        max_iterations: int = 5
    ):
        self.triage_agent = triage_agent or TriageAgent()
        self.resolution_agent = resolution_agent or ResolutionAgent()
        self.compliance_agent = compliance_agent or ComplianceAgent()
        self.max_iterations = max_iterations
        
        # In-memory ticket storage
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._workflow_results: Dict[str, WorkflowResult] = {}
        
        # Build the workflow graph
        self.graph = self._build_graph()
        self.memory = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.memory)
        
        logger.info("orchestrator_initialized", max_iterations=max_iterations)
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(OrchestratorState)
        
        # Add nodes
        workflow.add_node("triage", self._triage_node)
        workflow.add_node("resolve", self._resolve_node)
        workflow.add_node("compliance_check", self._compliance_node)
        workflow.add_node("escalate", self._escalate_node)
        workflow.add_node("request_info", self._request_info_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Set entry point
        workflow.set_entry_point("triage")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "triage",
            self._route_after_triage,
            {
                "auto_resolve": "resolve",
                "agent_resolution": "compliance_check",
                "human_escalation": "escalate",
                "information_request": "request_info"
            }
        )
        
        workflow.add_conditional_edges(
            "compliance_check",
            self._route_after_compliance,
            {
                "approved": "resolve",
                "denied": "escalate"
            }
        )
        
        workflow.add_conditional_edges(
            "resolve",
            self._route_after_resolution,
            {
                "success": "finalize",
                "retry": "resolve",
                "escalate": "escalate"
            }
        )
        
        workflow.add_edge("escalate", "finalize")
        workflow.add_edge("request_info", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow
    
    def store_ticket(self, ticket_id: str, ticket_data: Dict[str, Any]) -> None:
        """Store ticket data for later retrieval."""
        self._tickets[ticket_id] = {
            **ticket_data,
            "created_at": datetime.utcnow().isoformat(),
            "status": "new"
        }
    
    async def get_workflow_status(self, ticket_id: str) -> Dict[str, Any]:
        """Get the current status of a ticket workflow."""
        # Check if we have a completed result
        if ticket_id in self._workflow_results:
            result = self._workflow_results[ticket_id]
            return {
                "ticket_id": ticket_id,
                "status": result.status.value,
                "resolution_summary": result.resolution_summary,
                "actions_taken": result.actions_taken,
                "escalated": result.escalated,
                "escalation_reason": result.escalation_reason,
                "completed": True
            }
        
        # Check if ticket exists
        if ticket_id in self._tickets:
            ticket = self._tickets[ticket_id]
            return {
                "ticket_id": ticket_id,
                "status": ticket.get("status", "unknown"),
                "title": ticket.get("title"),
                "description": ticket.get("description"),
                "category": ticket.get("category"),
                "priority": ticket.get("priority"),
                "created_at": ticket.get("created_at"),
                "completed": False
            }
        
        # Ticket not found
        return {
            "ticket_id": ticket_id,
            "status": "not_found",
            "error": f"Ticket {ticket_id} not found",
            "completed": False
        }
    
    async def run(
        self,
        ticket_id: str,
        title: str,
        description: str,
        user_email: Optional[str] = None,
        category: Optional[TicketCategory] = None,
        priority: Optional[TicketPriority] = None
    ) -> WorkflowResult:
        """Run the orchestration workflow for a ticket."""
        logger.info("workflow_started", ticket_id=ticket_id)
        start_time = datetime.utcnow()
        
        # Update ticket status
        if ticket_id in self._tickets:
            self._tickets[ticket_id]["status"] = "processing"
        
        # Initialize state
        initial_state: OrchestratorState = {
            "ticket_id": ticket_id,
            "ticket_title": title,
            "ticket_description": description,
            "ticket_category": category.value if category else None,
            "ticket_priority": priority.value if priority else None,
            "user_email": user_email,
            "status": WorkflowStatus.PENDING.value,
            "current_agent": None,
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "triage_result": None,
            "resolution_result": None,
            "compliance_result": None,
            "messages": [],
            "actions_taken": [],
            "next_step": None,
            "requires_human": False,
            "escalation_reason": None,
            "start_time": start_time.isoformat(),
            "end_time": None,
            "total_cost_tokens": 0
        }
        
        # Run the workflow
        config = {"configurable": {"thread_id": ticket_id}}
        final_state = await self.app.ainvoke(initial_state, config)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Build result
        result = WorkflowResult(
            ticket_id=ticket_id,
            status=WorkflowStatus(final_state["status"]),
            resolution_summary=self._build_summary(final_state),
            actions_taken=final_state["actions_taken"],
            triage_result=TriageResult(**final_state["triage_result"]) if final_state.get("triage_result") else None,
            resolution_result=ResolutionResult(**final_state["resolution_result"]) if final_state.get("resolution_result") else None,
            escalated=final_state.get("requires_human", False),
            escalation_reason=final_state.get("escalation_reason"),
            total_duration_seconds=duration,
            iteration_count=final_state["iteration_count"]
        )
        
        # Store result for later retrieval
        self._workflow_results[ticket_id] = result
        
        # Update ticket status
        if ticket_id in self._tickets:
            self._tickets[ticket_id]["status"] = result.status.value
        
        logger.info(
            "workflow_completed",
            ticket_id=ticket_id,
            status=result.status.value,
            duration=duration
        )
        
        return result
    
    async def _triage_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute triage agent."""
        logger.debug("executing_triage", ticket_id=state["ticket_id"])
        
        result = await self.triage_agent.analyze(
            ticket_id=state["ticket_id"],
            title=state["ticket_title"],
            description=state["ticket_description"],
            user_email=state.get("user_email")
        )
        
        return {
            "status": WorkflowStatus.TRIAGING.value,
            "current_agent": "triage_agent",
            "triage_result": result.model_dump(),
            "ticket_category": result.category.value,
            "ticket_priority": result.priority.value,
            "messages": [{
                "agent": "triage_agent",
                "content": f"Classified as {result.category.value} ({result.priority.value})",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Triage: {result.decision.value}"]
        }
    
    async def _compliance_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute compliance validation."""
        logger.debug("executing_compliance_check", ticket_id=state["ticket_id"])
        
        triage_result = state.get("triage_result", {})
        
        is_compliant = await self.compliance_agent.validate_resolution_plan(
            ticket_id=state["ticket_id"],
            category=triage_result.get("category"),
            suggested_path=triage_result.get("suggested_resolution_path", "")
        )
        
        return {
            "compliance_result": {"approved": is_compliant},
            "messages": [{
                "agent": "compliance_agent",
                "content": f"Compliance check: {'Approved' if is_compliant else 'Denied'}",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Compliance: {'Approved' if is_compliant else 'Requires Review'}"]
        }
    
    async def _resolve_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute resolution agent."""
        logger.debug("executing_resolution", ticket_id=state["ticket_id"])
        
        triage_result = state.get("triage_result", {})
        iteration = state.get("iteration_count", 0) + 1
        
        result = await self.resolution_agent.resolve(
            ticket_id=state["ticket_id"],
            title=state["ticket_title"],
            description=state["ticket_description"],
            category=TicketCategory(triage_result.get("category", "other")),
            priority=TicketPriority(triage_result.get("priority", "medium")),
            user_email=state.get("user_email")
        )
        
        return {
            "status": WorkflowStatus.RESOLVING.value,
            "current_agent": "resolution_agent",
            "resolution_result": result.model_dump(),
            "iteration_count": iteration,
            "messages": [{
                "agent": "resolution_agent",
                "content": result.resolution_summary,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": result.actions_taken
        }
    
    async def _escalate_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Handle escalation to human operators."""
        logger.debug("executing_escalation", ticket_id=state["ticket_id"])
        
        reason = state.get("escalation_reason") or "Requires human expertise"
        
        return {
            "status": WorkflowStatus.ESCALATING.value,
            "requires_human": True,
            "escalation_reason": reason,
            "messages": [{
                "agent": "escalation_agent",
                "content": f"Escalated: {reason}",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Escalated to human: {reason}"]
        }
    
    async def _request_info_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Request additional information from user."""
        logger.debug("requesting_info", ticket_id=state["ticket_id"])
        
        return {
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "messages": [{
                "agent": "system",
                "content": "Additional information requested from user",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": ["Requested additional information"]
        }
    
    async def _finalize_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Finalize the workflow."""
        logger.debug("finalizing_workflow", ticket_id=state["ticket_id"])
        
        final_status = WorkflowStatus.COMPLETED
        if state.get("requires_human"):
            final_status = WorkflowStatus.ESCALATING
        elif state.get("resolution_result", {}).get("success") is False:
            final_status = WorkflowStatus.FAILED
        
        return {
            "status": final_status.value,
            "end_time": datetime.utcnow().isoformat(),
            "messages": [{
                "agent": "system",
                "content": f"Workflow finalized with status: {final_status.value}",
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
    
    def _route_after_triage(self, state: OrchestratorState) -> str:
        """Determine next step after triage."""
        triage_result = state.get("triage_result", {})
        decision = triage_result.get("decision", "agent_resolution")
        
        routing = {
            "auto_resolve": "auto_resolve",
            "agent_resolution": "agent_resolution",
            "human_escalation": "human_escalation",
            "information_request": "information_request"
        }
        
        return routing.get(decision, "agent_resolution")
    
    def _route_after_compliance(self, state: OrchestratorState) -> str:
        """Determine next step after compliance check."""
        compliance_result = state.get("compliance_result", {})
        
        if compliance_result.get("approved", False):
            return "approved"
        return "denied"
    
    def _route_after_resolution(self, state: OrchestratorState) -> str:
        """Determine next step after resolution attempt."""
        resolution_result = state.get("resolution_result", {})
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 5)
        
        if resolution_result.get("success", False):
            return "success"
        
        if iteration < max_iterations:
            return "retry"
        
        return "escalate"
    
    def _build_summary(self, state: OrchestratorState) -> str:
        """Build a human-readable summary of the workflow."""
        parts = []
        
        if state.get("triage_result"):
            tr = state["triage_result"]
            parts.append(f"Category: {tr.get('category', 'N/A')}, Priority: {tr.get('priority', 'N/A')}")
        
        if state.get("resolution_result"):
            rr = state["resolution_result"]
            parts.append(f"Resolution: {'Success' if rr.get('success') else 'Failed'}")
        
        if state.get("requires_human"):
            parts.append(f"Escalated: {state.get('escalation_reason', 'N/A')}")
        
        return " | ".join(parts) if parts else "Workflow completed"