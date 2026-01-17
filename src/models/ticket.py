"""
Data Models Module

Pydantic models for tickets, agent states, and workflow data.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Ticket Models
# ============================================================================

class TicketStatus(str, Enum):
    """Status of a support ticket."""
    NEW = "new"
    TRIAGING = "triaging"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    PENDING_APPROVAL = "pending_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class TicketPriority(str, Enum):
    """Priority level of a ticket."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketCategory(str, Enum):
    """Category of IT support ticket."""
    NETWORK = "network"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    ACCESS = "access"
    EMAIL = "email"
    OTHER = "other"


class Ticket(BaseModel):
    """Represents an IT support ticket."""
    ticket_id: str
    title: str
    description: str
    status: TicketStatus = TicketStatus.NEW
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.OTHER
    
    # User information
    submitter_email: Optional[str] = None
    submitter_name: Optional[str] = None
    department: Optional[str] = None
    
    # Assignment
    assigned_to: Optional[str] = None
    assigned_agent: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    # Resolution
    resolution_notes: Optional[str] = None
    resolution_time_minutes: Optional[int] = None
    
    # Metadata
    attachments: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "INC001234",
                "title": "Cannot access VPN",
                "description": "Getting timeout errors when connecting",
                "status": "new",
                "priority": "medium",
                "category": "network",
                "submitter_email": "john.doe@company.com"
            }
        }


# ============================================================================
# Agent State Models
# ============================================================================

class AgentAction(BaseModel):
    """Represents a single action taken by an agent."""
    action_type: str
    summary: str
    success: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: Optional[str] = None
    input_params: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: Optional[float] = None


class ActionResult(BaseModel):
    """Result of a tool execution."""
    success: bool
    tool_name: str
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    requires_approval: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """State of an agent during workflow execution."""
    agent_name: str
    status: str  # pending, running, completed, failed
    output: Optional[Dict[str, Any]] = None
    actions: List[AgentAction] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def add_action(self, action: AgentAction):
        """Add an action to the state."""
        self.actions.append(action)
    
    def get_last_action(self) -> Optional[AgentAction]:
        """Get the most recent action."""
        return self.actions[-1] if self.actions else None
    
    def get_successful_actions(self) -> List[AgentAction]:
        """Get all successful actions."""
        return [a for a in self.actions if a.success]


# ============================================================================
# Workflow Models
# ============================================================================

class WorkflowStep(BaseModel):
    """A step in a workflow."""
    step_id: str
    name: str
    agent: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowExecution(BaseModel):
    """Represents a complete workflow execution."""
    execution_id: str
    workflow_name: str
    ticket_id: str
    status: str
    steps: List[WorkflowStep] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
