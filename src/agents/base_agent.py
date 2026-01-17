"""
Base Agent Module - Anthropic Claude Version

Abstract base class for all AI agents in the AgentOps platform.
Uses Anthropic's Claude API with rate limiting support.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import asyncio
import structlog
from pydantic import BaseModel, Field

import anthropic
from anthropic import RateLimitError, APIError

from src.models.agent_state import AgentState, AgentAction, ActionResult
from src.utils.security import SecurityContext, validate_action_permissions
from src.utils.observability import trace_agent_action, MetricsCollector
from src.utils.rate_limiter import RateLimiter


logger = structlog.get_logger(__name__)


class AgentCapability(str, Enum):
    """Enumeration of agent capabilities for RBAC."""
    READ_TICKET = "read_ticket"
    UPDATE_TICKET = "update_ticket"
    RESOLVE_TICKET = "resolve_ticket"
    ESCALATE_TICKET = "escalate_ticket"
    EXECUTE_REMEDIATION = "execute_remediation"
    ACCESS_KNOWLEDGE_BASE = "access_knowledge_base"
    SEND_NOTIFICATION = "send_notification"
    MODIFY_USER_ACCOUNT = "modify_user_account"


class AgentConfig(BaseModel):
    """Configuration for agent initialization."""
    name: str
    description: str
    model: str = "claude-sonnet-4-20250514"  # Anthropic Claude model
    temperature: float = 0.1
    max_tokens: int = 4096
    capabilities: List[AgentCapability] = Field(default_factory=list)
    require_compliance_check: bool = True
    max_retries: int = 3
    timeout_seconds: int = 60
    # Rate limiting config
    requests_per_minute: int = 50
    tokens_per_minute: int = 100000


class AgentContext(BaseModel):
    """Context passed to agent during execution."""
    ticket_id: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    security_context: Optional[Dict[str, Any]] = None
    retrieved_knowledge: Optional[List[Dict[str, Any]]] = None
    previous_actions: List[AgentAction] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents using Anthropic Claude.
    
    Provides:
    - Claude API interaction with configurable models
    - Built-in rate limiting
    - Tool registration and execution
    - State management across conversation turns
    - Security and compliance validation
    - Observability (tracing, metrics, logging)
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.tools: Dict[str, callable] = {}
        self.metrics = MetricsCollector(agent_name=config.name)
        
        # Initialize Anthropic client
        self._client = anthropic.AsyncAnthropic()  # Uses ANTHROPIC_API_KEY env var
        
        # Initialize rate limiter
        self._rate_limiter = RateLimiter(
            requests_per_minute=config.requests_per_minute,
            tokens_per_minute=config.tokens_per_minute
        )
        
        logger.info(
            "agent_initialized",
            agent_name=self.name,
            model=config.model,
            capabilities=[c.value for c in config.capabilities]
        )
    
    def register_tool(self, name: str, func: callable, description: str, 
                     required_capability: Optional[AgentCapability] = None):
        """Register a tool that the agent can use."""
        self.tools[name] = {
            "function": func,
            "description": description,
            "required_capability": required_capability
        }
        logger.debug("tool_registered", agent=self.name, tool=name)
    
    def get_available_tools(self, security_context: Optional[SecurityContext] = None) -> List[Dict[str, Any]]:
        """Get list of tools available to the agent based on permissions."""
        available = []
        for name, tool in self.tools.items():
            required_cap = tool.get("required_capability")
            if required_cap and required_cap not in self.config.capabilities:
                continue
                
            if security_context and required_cap:
                if not validate_action_permissions(security_context, required_cap.value):
                    continue
            
            available.append({
                "name": name,
                "description": tool["description"]
            })
        
        return available
    
    @trace_agent_action
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any],
                          context: AgentContext) -> ActionResult:
        """Execute a registered tool with given parameters."""
        if tool_name not in self.tools:
            return ActionResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                tool_name=tool_name
            )
        
        tool = self.tools[tool_name]
        
        # Compliance check before execution
        if self.config.require_compliance_check:
            from src.agents.compliance_agent import ComplianceAgent
            compliance = ComplianceAgent()
            is_compliant = await compliance.validate_action(
                action_type=tool_name,
                parameters=parameters,
                context=context
            )
            if not is_compliant:
                logger.warning("action_blocked_compliance", tool=tool_name, agent=self.name)
                return ActionResult(
                    success=False,
                    error="Action blocked by compliance check",
                    tool_name=tool_name,
                    requires_approval=True
                )
        
        try:
            start_time = datetime.utcnow()
            result = await tool["function"](**parameters)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.metrics.record_tool_execution(
                tool_name=tool_name,
                success=True,
                execution_time=execution_time
            )
            
            logger.info("tool_executed", agent=self.name, tool=tool_name, execution_time=execution_time)
            
            return ActionResult(
                success=True,
                output=result,
                tool_name=tool_name,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error("tool_execution_failed", agent=self.name, tool=tool_name, error=str(e))
            self.metrics.record_tool_execution(tool_name=tool_name, success=False)
            
            return ActionResult(
                success=False,
                error=str(e),
                tool_name=tool_name
            )
    
    async def think(self, prompt: str, context: AgentContext) -> str:
        """
        Generate a response from Claude with rate limiting and retries.
        """
        messages = self._build_messages(prompt, context)
        
        for attempt in range(self.config.max_retries):
            try:
                # Wait for rate limiter
                await self._rate_limiter.acquire()
                
                # Call Claude API
                response = await self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=self._get_system_prompt(),
                    messages=messages
                )
                
                # Track token usage for rate limiting
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self._rate_limiter.record_tokens(input_tokens + output_tokens)
                
                # Extract text response
                return response.content[0].text
                
            except RateLimitError as e:
                wait_time = min(2 ** attempt * 10, 60)  # Exponential backoff, max 60s
                logger.warning(
                    "rate_limit_hit",
                    agent=self.name,
                    attempt=attempt + 1,
                    wait_time=wait_time
                )
                await asyncio.sleep(wait_time)
                
            except APIError as e:
                logger.error("api_error", agent=self.name, error=str(e), attempt=attempt + 1)
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error("llm_invocation_failed", agent=self.name, error=str(e))
                raise
        
        raise Exception(f"Failed after {self.config.max_retries} retries")
    
    def _build_messages(self, prompt: str, context: AgentContext) -> List[Dict[str, str]]:
        """Build message list for Claude."""
        messages = []
        
        # Add retrieved knowledge context as a user message prefix
        context_parts = []
        
        if context.retrieved_knowledge:
            knowledge_context = self._format_knowledge_context(context.retrieved_knowledge)
            context_parts.append(f"Relevant knowledge:\n{knowledge_context}")
        
        if context.previous_actions:
            action_history = self._format_action_history(context.previous_actions)
            context_parts.append(f"Previous actions taken:\n{action_history}")
        
        # Combine context with user prompt
        full_prompt = prompt
        if context_parts:
            full_prompt = "\n\n".join(context_parts) + f"\n\nUser request:\n{prompt}"
        
        messages.append({"role": "user", "content": full_prompt})
        
        return messages
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentState:
        """Execute the agent's main logic."""
        pass
    
    def _format_knowledge_context(self, knowledge: List[Dict[str, Any]]) -> str:
        """Format retrieved knowledge for inclusion in prompt."""
        formatted = []
        for idx, doc in enumerate(knowledge, 1):
            formatted.append(f"[{idx}] {doc.get('content', '')[:500]}...")
            if doc.get('metadata'):
                formatted.append(f"   Source: {doc['metadata'].get('source', 'Unknown')}")
        return "\n".join(formatted)
    
    def _format_action_history(self, actions: List[AgentAction]) -> str:
        """Format action history for inclusion in prompt."""
        formatted = []
        for action in actions[-5:]:
            status = "✓" if action.success else "✗"
            formatted.append(f"{status} {action.action_type}: {action.summary}")
        return "\n".join(formatted)
    
    def get_confidence_score(self, state: AgentState) -> float:
        """Calculate confidence score for the current state."""
        if not state.actions:
            return 0.5
        
        successful = sum(1 for a in state.actions if a.success)
        action_score = successful / len(state.actions)
        knowledge_score = state.metadata.get("knowledge_relevance_score", 0.5)
        confidence = (action_score * 0.6) + (knowledge_score * 0.4)
        
        return min(max(confidence, 0.0), 1.0)


class AgentResponse(BaseModel):
    """Structured response from an agent."""
    agent_name: str
    state: AgentState
    confidence: float
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None
    next_suggested_action: Optional[str] = None
    execution_time_seconds: float