"""
Agent Orchestrator Module

LangGraph-based workflow orchestration for multi-agent IT operations.
Implements a state machine that coordinates triage, resolution, escalation,
and compliance agents for end-to-end ticket handling.
"""

from typing import Any, Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
from enum import Enum
import operator
import structlog
from pydantic import BaseModel

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.triage_agent import TriageAgent, TriageResult, TriageDecision
from src.agents.resolution_agent import ResolutionAgent, ResolutionResult
from src.agents.compliance_agent import ComplianceAgent
from src.models.ticket import TicketStatus, TicketCategory, TicketPriority


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
    ticket_id: str
    ticket_title: str
    ticket_description: str
    ticket_category: Optional[str]
    ticket_priority: Optional[str]
    user_email: Optional[str]
    status: str
    current_agent: Optional[str]
    iteration_count: int
    max_iterations: int
    triage_result: Optional[Dict[str, Any]]
    resolution_result: Optional[Dict[str, Any]]
    compliance_result: Optional[Dict[str, Any]]
    messages: Annotated[List[Dict[str, Any]], operator.add]
    actions_taken: Annotated[List[str], operator.add]
    next_step: Optional[str]
    requires_human: bool
    escalation_reason: Optional[str]
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
    
    Workflow:
    START → TRIAGE → [Decision]
                      ├─ AUTO_RESOLVE → RESOLVE → VERIFY → END
                      ├─ AGENT_RESOLUTION → COMPLIANCE → RESOLVE → END
                      ├─ HUMAN_ESCALATION → ESCALATE → END
                      └─ INFO_REQUEST → REQUEST_INFO → END
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
        
        self.graph = self._build_graph()
        self.memory = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.memory)
        
        logger.info("orchestrator_initialized", max_iterations=max_iterations)
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(OrchestratorState)
        
        workflow.add_node("triage", self._triage_node)
        workflow.add_node("resolve", self._resolve_node)
        workflow.add_node("compliance_check", self._compliance_node)
        workflow.add_node("escalate", self._escalate_node)
        workflow.add_node("request_info", self._request_info_node)
        workflow.add_node("finalize", self._finalize_node)
        
        workflow.set_entry_point("triage")
        
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
            {"approved": "resolve", "denied": "escalate"}
        )
        
        workflow.add_conditional_edges(
            "resolve",
            self._route_after_resolution,
            {"success": "finalize", "retry": "resolve", "escalate": "escalate"}
        )
        
        workflow.add_edge("escalate", "finalize")
        workflow.add_edge("request_info", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow
    
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
        
        config = {"configurable": {"thread_id": ticket_id}}
        final_state = await self.app.ainvoke(initial_state, config)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        return WorkflowResult(
            ticket_id=ticket_id,
            status=WorkflowStatus(final_state["status"]),
            resolution_summary=self._build_summary(final_state),
            actions_taken=final_state["actions_taken"],
            escalated=final_state.get("requires_human", False),
            escalation_reason=final_state.get("escalation_reason"),
            total_duration_seconds=duration,
            iteration_count=final_state["iteration_count"]
        )
    
    async def _triage_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute triage agent."""
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
                "content": f"Classified: {result.category.value} ({result.priority.value})",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Triage: {result.decision.value}"]
        }
    
    async def _compliance_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute compliance validation."""
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
                "content": f"Compliance: {'Approved' if is_compliant else 'Denied'}",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Compliance: {'Approved' if is_compliant else 'Review Required'}"]
        }
    
    async def _resolve_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute resolution agent."""
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
        triage_result = state.get("triage_result", {})
        resolution_result = state.get("resolution_result", {})
        
        reason = (
            triage_result.get("reasoning", "") or
            resolution_result.get("escalation_reason", "") or
            "Requires human expertise"
        )
        
        return {
            "status": WorkflowStatus.ESCALATING.value,
            "current_agent": "escalation_agent",
            "requires_human": True,
            "escalation_reason": reason,
            "messages": [{
                "agent": "escalation_agent",
                "content": f"Escalating: {reason}",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": [f"Escalated: {reason[:50]}..."]
        }
    
    async def _request_info_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Request additional information from user."""
        return {
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "messages": [{
                "agent": "orchestrator",
                "content": "Requesting additional information",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "actions_taken": ["Requested additional information"]
        }
    
    async def _finalize_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Finalize the workflow."""
        resolution_result = state.get("resolution_result", {})
        success = resolution_result.get("success", False)
        escalated = state.get("requires_human", False)
        
        final_status = (
            WorkflowStatus.COMPLETED if success and not escalated
            else WorkflowStatus.ESCALATING if escalated
            else WorkflowStatus.FAILED
        )
        
        return {
            "status": final_status.value,
            "end_time": datetime.utcnow().isoformat(),
            "messages": [{
                "agent": "orchestrator",
                "content": f"Workflow completed: {final_status.value}",
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
    
    def _route_after_triage(self, state: OrchestratorState) -> str:
        """Determine next step based on triage result."""
        triage_result = state.get("triage_result", {})
        decision = triage_result.get("decision", "agent_resolution")
        
        routing_map = {
            TriageDecision.AUTO_RESOLVE.value: "auto_resolve",
            TriageDecision.AGENT_RESOLUTION.value: "agent_resolution",
            TriageDecision.HUMAN_ESCALATION.value: "human_escalation",
            TriageDecision.INFORMATION_REQUEST.value: "information_request"
        }
        
        return routing_map.get(decision, "agent_resolution")
    
    def _route_after_compliance(self, state: OrchestratorState) -> str:
        """Route based on compliance check result."""
        compliance_result = state.get("compliance_result", {})
        return "approved" if compliance_result.get("approved", False) else "denied"
    
    def _route_after_resolution(self, state: OrchestratorState) -> str:
        """Route based on resolution result."""
        resolution_result = state.get("resolution_result", {})
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 5)
        
        if resolution_result.get("success", False):
            return "success"
        elif iteration < max_iterations:
            return "retry"
        else:
            return "escalate"
    
    def _build_summary(self, state: OrchestratorState) -> str:
        """Build a human-readable summary of the workflow."""
        resolution_result = state.get("resolution_result", {})
        
        if resolution_result.get("success"):
            return resolution_result.get("resolution_summary", "Issue resolved")
        elif state.get("requires_human"):
            return f"Escalated: {state.get('escalation_reason', 'Unknown')}"
        else:
            return "Resolution in progress"
