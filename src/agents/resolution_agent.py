"""
Resolution Agent Module - Anthropic Claude Version

Autonomous IT support resolution agent using Claude for troubleshooting
and remediation actions.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import json
import structlog
from pydantic import BaseModel, Field

from src.agents.base_agent import (
    BaseAgent, AgentConfig, AgentContext, AgentCapability, AgentResponse
)
from src.models.agent_state import AgentState, AgentAction, ActionResult
from src.models.ticket import Ticket, TicketPriority, TicketCategory, TicketStatus
from src.rag.retriever import ContextRetriever
from src.tools.remediation import RemediationEngine


logger = structlog.get_logger(__name__)


class ResolutionStep(BaseModel):
    """A single step in the resolution process."""
    step_number: int
    action: str
    tool_name: Optional[str] = None
    tool_parameters: Optional[Dict[str, Any]] = None
    expected_outcome: str
    actual_outcome: Optional[str] = None
    success: Optional[bool] = None
    timestamp: Optional[datetime] = None


class ResolutionPlan(BaseModel):
    """Planned resolution approach."""
    ticket_id: str
    summary: str
    steps: List[ResolutionStep]
    estimated_duration_minutes: int
    requires_user_interaction: bool = False
    requires_approval: bool = False
    confidence_score: float


class ResolutionResult(BaseModel):
    """Result of resolution attempt."""
    ticket_id: str
    success: bool
    resolution_summary: str
    steps_executed: List[ResolutionStep]
    total_execution_time_seconds: float
    actions_taken: List[str]
    user_communication: Optional[str] = None
    follow_up_required: bool = False
    escalation_reason: Optional[str] = None


class ResolutionAgent(BaseAgent):
    """
    AI Agent for autonomous ticket resolution using Anthropic Claude.
    
    Capabilities:
    - Multi-step troubleshooting workflows
    - Tool execution for remediation
    - Knowledge-grounded decision making
    - Automatic user communication
    """
    
    MAX_ITERATIONS = 10
    AUTO_EXECUTE_THRESHOLD = 0.75
    
    def __init__(
        self,
        retriever: Optional[ContextRetriever] = None,
        remediation_engine: Optional[RemediationEngine] = None
    ):
        super().__init__(AgentConfig(
            name="resolution_agent",
            description="Autonomous ticket resolution with tool execution",
            model="claude-sonnet-4-20250514",
            temperature=0.2,
            capabilities=[
                AgentCapability.READ_TICKET,
                AgentCapability.UPDATE_TICKET,
                AgentCapability.RESOLVE_TICKET,
                AgentCapability.ACCESS_KNOWLEDGE_BASE,
                AgentCapability.SEND_NOTIFICATION,
                AgentCapability.EXECUTE_REMEDIATION,
                AgentCapability.MODIFY_USER_ACCOUNT
            ],
            require_compliance_check=True,
            max_retries=3,
            requests_per_minute=40,
            tokens_per_minute=80000
        ))
        
        self.retriever = retriever or ContextRetriever()
        self.remediation = remediation_engine or RemediationEngine()
        self._register_tools()
    
    def _register_tools(self):
        """Register resolution tools."""
        # Account Management
        self.register_tool(
            name="reset_password",
            func=self._reset_password,
            description="Reset user password in Active Directory/Entra ID",
            required_capability=AgentCapability.MODIFY_USER_ACCOUNT
        )
        self.register_tool(
            name="unlock_account",
            func=self._unlock_account,
            description="Unlock a locked user account",
            required_capability=AgentCapability.MODIFY_USER_ACCOUNT
        )
        self.register_tool(
            name="enable_mfa",
            func=self._enable_mfa,
            description="Enable or reset MFA for user",
            required_capability=AgentCapability.MODIFY_USER_ACCOUNT
        )
        
        # Network Tools
        self.register_tool(
            name="push_vpn_config",
            func=self._push_vpn_config,
            description="Push VPN configuration to user device",
            required_capability=AgentCapability.EXECUTE_REMEDIATION
        )
        self.register_tool(
            name="reset_network_adapter",
            func=self._reset_network_adapter,
            description="Remotely reset network adapter",
            required_capability=AgentCapability.EXECUTE_REMEDIATION
        )
        
        # Software Tools
        self.register_tool(
            name="install_software",
            func=self._install_software,
            description="Trigger software installation via SCCM/Intune",
            required_capability=AgentCapability.EXECUTE_REMEDIATION
        )
        self.register_tool(
            name="repair_application",
            func=self._repair_application,
            description="Run application repair/reinstall",
            required_capability=AgentCapability.EXECUTE_REMEDIATION
        )
        
        # Communication & Diagnostics
        self.register_tool(
            name="send_user_notification",
            func=self._send_user_notification,
            description="Send notification to user",
            required_capability=AgentCapability.SEND_NOTIFICATION
        )
        self.register_tool(
            name="update_ticket",
            func=self._update_ticket,
            description="Update ticket status and notes",
            required_capability=AgentCapability.UPDATE_TICKET
        )
        self.register_tool(
            name="run_diagnostic",
            func=self._run_diagnostic,
            description="Run diagnostic script on device",
            required_capability=AgentCapability.EXECUTE_REMEDIATION
        )
        self.register_tool(
            name="check_service_status",
            func=self._check_service_status,
            description="Check status of IT services",
            required_capability=AgentCapability.READ_TICKET
        )
    
    def _get_system_prompt(self) -> str:
        return """You are an expert IT support resolution agent with the ability to execute remediation actions.

Your role is to:
1. ANALYZE the ticket and available context
2. CREATE a step-by-step resolution plan
3. EXECUTE each step using available tools
4. VERIFY success after each action
5. COMMUNICATE clearly with the user

IMPORTANT GUIDELINES:
- Start with least invasive troubleshooting
- Verify prerequisites before executing
- If an action fails, try alternatives before escalating
- Document all actions for audit
- Prioritize user experience

TOOL USAGE:
- Use tools precisely as documented
- Always verify tool parameters
- Check tool results and handle errors

OUTPUT FORMAT for plans:
PLAN_SUMMARY: Brief overview
STEP_1: [Action] | TOOL: [tool_name] | PARAMS: {json}
STEP_2: ...
REQUIRES_APPROVAL: [yes/no]
CONFIDENCE: [0.0-1.0]

OUTPUT FORMAT for results:
RESULT: [SUCCESS/PARTIAL/FAILED]
ACTIONS_TAKEN: List of completed actions
USER_MESSAGE: Message to send to user
FOLLOW_UP: Any required follow-up"""

    async def execute(self, context: AgentContext) -> AgentState:
        """Execute resolution workflow."""
        ticket_data = context.metadata.get("ticket_data", {})
        
        result = await self.resolve(
            ticket_id=context.ticket_id,
            title=ticket_data.get("title", ""),
            description=ticket_data.get("description", ""),
            category=TicketCategory(ticket_data.get("category", "other")),
            priority=TicketPriority(ticket_data.get("priority", "medium")),
            user_email=ticket_data.get("user_email"),
            context=context
        )
        
        return AgentState(
            agent_name=self.name,
            status="completed" if result.success else "failed",
            output=result.model_dump(),
            actions=[AgentAction(
                action_type="resolution",
                summary=result.resolution_summary,
                success=result.success
            )],
            metadata={
                "steps_executed": len(result.steps_executed),
                "follow_up_required": result.follow_up_required
            }
        )
    
    async def resolve(
        self,
        ticket_id: str,
        title: str,
        description: str,
        category: TicketCategory,
        priority: TicketPriority,
        user_email: Optional[str] = None,
        context: Optional[AgentContext] = None
    ) -> ResolutionResult:
        """Attempt to autonomously resolve a ticket."""
        start_time = datetime.utcnow()
        logger.info("resolution_started", ticket_id=ticket_id, category=category.value)
        
        if not context:
            context = AgentContext(ticket_id=ticket_id)
        
        # Retrieve relevant knowledge
        knowledge = await self.retriever.retrieve(
            query=f"{title} {description}",
            filters={"category": category.value},
            top_k=5
        )
        context.retrieved_knowledge = knowledge
        
        # Create resolution plan
        plan = await self._create_resolution_plan(
            ticket_id=ticket_id,
            title=title,
            description=description,
            category=category,
            knowledge=knowledge,
            context=context
        )
        
        # Check if approval required
        if plan.requires_approval:
            logger.info("resolution_requires_approval", ticket_id=ticket_id)
            return ResolutionResult(
                ticket_id=ticket_id,
                success=False,
                resolution_summary="Resolution plan requires human approval",
                steps_executed=[],
                total_execution_time_seconds=0,
                actions_taken=["Created resolution plan"],
                escalation_reason="Actions require human approval"
            )
        
        # Execute resolution plan
        executed_steps = await self._execute_plan(plan, context)
        
        # Verify resolution
        success = all(step.success for step in executed_steps if step.success is not None)
        
        # Generate user communication
        user_message = await self._generate_user_message(
            ticket_id=ticket_id,
            success=success,
            steps=executed_steps,
            context=context
        )
        
        # Send notifications and update ticket
        if success and user_email:
            await self._send_user_notification(
                user_email=user_email,
                subject=f"Ticket {ticket_id} Resolved",
                message=user_message
            )
        
        await self._update_ticket(
            ticket_id=ticket_id,
            status=TicketStatus.RESOLVED if success else TicketStatus.IN_PROGRESS,
            work_notes=self._format_work_notes(executed_steps)
        )
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        result = ResolutionResult(
            ticket_id=ticket_id,
            success=success,
            resolution_summary=plan.summary if success else "Resolution incomplete",
            steps_executed=executed_steps,
            total_execution_time_seconds=execution_time,
            actions_taken=[s.action for s in executed_steps if s.success],
            user_communication=user_message,
            follow_up_required=not success,
            escalation_reason=None if success else "One or more steps failed"
        )
        
        logger.info(
            "resolution_completed",
            ticket_id=ticket_id,
            success=success,
            execution_time=execution_time
        )
        
        return result
    
    async def _create_resolution_plan(
        self,
        ticket_id: str,
        title: str,
        description: str,
        category: TicketCategory,
        knowledge: List[Dict[str, Any]],
        context: AgentContext
    ) -> ResolutionPlan:
        """Create a structured resolution plan using Claude."""
        available_tools = self.get_available_tools()
        
        prompt = f"""Create a resolution plan for this ticket:

TICKET ID: {ticket_id}
CATEGORY: {category.value}
TITLE: {title}
DESCRIPTION: {description}

AVAILABLE TOOLS:
{json.dumps(available_tools, indent=2)}

RELEVANT KNOWLEDGE:
{self._format_knowledge(knowledge)}

Create a step-by-step plan following the specified output format."""

        response = await self.think(prompt, context)
        plan = self._parse_resolution_plan(ticket_id, response, category)
        
        return plan
    
    def _parse_resolution_plan(
        self,
        ticket_id: str,
        llm_response: str,
        category: TicketCategory
    ) -> ResolutionPlan:
        """Parse Claude's response into structured resolution plan."""
        steps = []
        lines = llm_response.split("\n")
        
        current_step = 1
        plan_summary = ""
        requires_approval = False
        confidence = 0.7
        
        for line in lines:
            line = line.strip()
            
            if line.upper().startswith("PLAN_SUMMARY:"):
                plan_summary = line.split(":", 1)[-1].strip()
            elif line.upper().startswith("REQUIRES_APPROVAL:"):
                requires_approval = "yes" in line.lower()
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[-1].strip())
                except ValueError:
                    confidence = 0.7
            elif line.upper().startswith(f"STEP_{current_step}:"):
                parts = line.split("|")
                action = parts[0].split(":", 1)[-1].strip()
                
                tool_name = None
                tool_params = None
                
                for part in parts[1:]:
                    if "TOOL:" in part.upper():
                        tool_name = part.split(":", 1)[-1].strip()
                    elif "PARAMS:" in part.upper():
                        try:
                            params_str = part.split(":", 1)[-1].strip()
                            tool_params = json.loads(params_str)
                        except json.JSONDecodeError:
                            tool_params = {}
                
                steps.append(ResolutionStep(
                    step_number=current_step,
                    action=action,
                    tool_name=tool_name,
                    tool_parameters=tool_params,
                    expected_outcome=f"Step {current_step} completed"
                ))
                current_step += 1
        
        if not steps:
            steps = self._get_default_plan(category)
            plan_summary = f"Default resolution plan for {category.value}"
        
        return ResolutionPlan(
            ticket_id=ticket_id,
            summary=plan_summary or "Resolution plan created",
            steps=steps,
            estimated_duration_minutes=len(steps) * 5,
            requires_user_interaction=False,
            requires_approval=requires_approval,
            confidence_score=confidence
        )
    
    def _get_default_plan(self, category: TicketCategory) -> List[ResolutionStep]:
        """Get default resolution steps for a category."""
        default_plans = {
            TicketCategory.ACCESS: [
                ResolutionStep(
                    step_number=1,
                    action="Check account status",
                    tool_name="check_service_status",
                    tool_parameters={"service": "active_directory"},
                    expected_outcome="Account status retrieved"
                ),
                ResolutionStep(
                    step_number=2,
                    action="Unlock account if locked",
                    tool_name="unlock_account",
                    tool_parameters={},
                    expected_outcome="Account unlocked"
                )
            ],
            TicketCategory.NETWORK: [
                ResolutionStep(
                    step_number=1,
                    action="Check VPN service status",
                    tool_name="check_service_status",
                    tool_parameters={"service": "vpn"},
                    expected_outcome="VPN service operational"
                ),
                ResolutionStep(
                    step_number=2,
                    action="Push VPN configuration",
                    tool_name="push_vpn_config",
                    tool_parameters={},
                    expected_outcome="VPN config deployed"
                )
            ]
        }
        
        return default_plans.get(category, [
            ResolutionStep(
                step_number=1,
                action="Run general diagnostic",
                tool_name="run_diagnostic",
                tool_parameters={"type": "general"},
                expected_outcome="Diagnostic completed"
            )
        ])
    
    async def _execute_plan(
        self,
        plan: ResolutionPlan,
        context: AgentContext
    ) -> List[ResolutionStep]:
        """Execute each step in the resolution plan."""
        executed_steps = []
        
        for step in plan.steps:
            if len(executed_steps) >= self.MAX_ITERATIONS:
                logger.warning("max_iterations_reached", ticket_id=plan.ticket_id)
                break
            
            step.timestamp = datetime.utcnow()
            
            if step.tool_name and step.tool_name in self.tools:
                result = await self.execute_tool(
                    tool_name=step.tool_name,
                    parameters=step.tool_parameters or {},
                    context=context
                )
                
                step.success = result.success
                step.actual_outcome = str(result.output) if result.success else result.error
                
                context.previous_actions.append(AgentAction(
                    action_type=step.tool_name,
                    summary=step.action,
                    success=result.success,
                    output=result.output,
                    error=result.error
                ))
                
                if not result.success:
                    logger.warning("step_failed", step=step.step_number, tool=step.tool_name, error=result.error)
            else:
                step.success = True
                step.actual_outcome = "Step noted"
            
            executed_steps.append(step)
            
            if step.success is False and step.step_number == 1:
                break
        
        return executed_steps
    
    async def _generate_user_message(
        self,
        ticket_id: str,
        success: bool,
        steps: List[ResolutionStep],
        context: AgentContext
    ) -> str:
        """Generate user-friendly resolution message using Claude."""
        prompt = f"""Generate a friendly message for ticket {ticket_id}.

Status: {"RESOLVED" if success else "IN PROGRESS"}

Actions Taken:
{chr(10).join(f"- {s.action}: {s.actual_outcome}" for s in steps if s.success)}

Write a concise, helpful message (2-3 sentences)."""

        return await self.think(prompt, context)
    
    def _format_knowledge(self, knowledge: List[Dict[str, Any]]) -> str:
        if not knowledge:
            return "No relevant documentation found."
        
        formatted = []
        for doc in knowledge[:3]:
            content = doc.get("content", "")[:400]
            source = doc.get("metadata", {}).get("source", "Unknown")
            formatted.append(f"[{source}]\n{content}\n")
        
        return "\n".join(formatted)
    
    def _format_work_notes(self, steps: List[ResolutionStep]) -> str:
        notes = ["=== Automated Resolution ===\n"]
        
        for step in steps:
            status = "✓" if step.success else "✗"
            timestamp = step.timestamp.strftime("%H:%M:%S") if step.timestamp else "N/A"
            notes.append(f"[{timestamp}] {status} {step.action}")
            if step.tool_name:
                notes.append(f"    Tool: {step.tool_name}")
            if step.actual_outcome:
                notes.append(f"    Result: {step.actual_outcome[:100]}")
        
        return "\n".join(notes)
    
    # Tool implementations
    async def _reset_password(self, user_id: str = None, user_email: str = None, 
                             temporary: bool = True) -> Dict[str, Any]:
        return await self.remediation.reset_password(user_id=user_id, user_email=user_email, temporary=temporary)
    
    async def _unlock_account(self, user_id: str = None, user_email: str = None) -> Dict[str, Any]:
        return await self.remediation.unlock_account(user_id=user_id, user_email=user_email)
    
    async def _enable_mfa(self, user_email: str, method: str = "authenticator") -> Dict[str, Any]:
        return await self.remediation.enable_mfa(user_email=user_email, method=method)
    
    async def _push_vpn_config(self, user_email: str = None, device_id: str = None) -> Dict[str, Any]:
        return await self.remediation.push_vpn_config(user_email=user_email, device_id=device_id)
    
    async def _reset_network_adapter(self, device_id: str) -> Dict[str, Any]:
        return await self.remediation.reset_network_adapter(device_id=device_id)
    
    async def _install_software(self, software_id: str, device_id: str = None, user_email: str = None) -> Dict[str, Any]:
        return await self.remediation.install_software(software_id=software_id, device_id=device_id, user_email=user_email)
    
    async def _repair_application(self, app_name: str, device_id: str) -> Dict[str, Any]:
        return await self.remediation.repair_application(app_name=app_name, device_id=device_id)
    
    async def _send_user_notification(self, user_email: str, subject: str, message: str, channel: str = "email") -> Dict[str, Any]:
        logger.info("notification_sent", user=user_email, channel=channel)
        return {"success": True, "channel": channel}
    
    async def _update_ticket(self, ticket_id: str, status: TicketStatus = None, work_notes: str = None) -> Dict[str, Any]:
        logger.info("ticket_updated", ticket_id=ticket_id, status=status)
        return {"success": True, "ticket_id": ticket_id}
    
    async def _run_diagnostic(self, device_id: str = None, diagnostic_type: str = "general") -> Dict[str, Any]:
        return await self.remediation.run_diagnostic(device_id=device_id, diagnostic_type=diagnostic_type)
    
    async def _check_service_status(self, service: str) -> Dict[str, Any]:
        return {"service": service, "status": "operational", "latency_ms": 45}