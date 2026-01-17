"""
Triage Agent Module - Anthropic Claude Version

Intelligent ticket classification and routing agent using Claude.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from src.agents.base_agent import (
    BaseAgent, AgentConfig, AgentContext, AgentCapability, AgentResponse
)
from src.models.agent_state import AgentState, AgentAction
from src.models.ticket import Ticket, TicketPriority, TicketCategory
from src.rag.retriever import ContextRetriever


logger = structlog.get_logger(__name__)


class TriageDecision(str, Enum):
    """Possible triage decisions."""
    AUTO_RESOLVE = "auto_resolve"
    AGENT_RESOLUTION = "agent_resolution"
    HUMAN_ESCALATION = "human_escalation"
    INFORMATION_REQUEST = "information_request"


class TriageResult(BaseModel):
    """Result of ticket triage analysis."""
    ticket_id: str
    category: TicketCategory
    priority: TicketPriority
    decision: TriageDecision
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_resolution_path: str
    relevant_runbooks: List[str] = Field(default_factory=list)
    similar_tickets: List[str] = Field(default_factory=list)
    estimated_resolution_time_minutes: Optional[int] = None
    reasoning: str
    requires_approval: bool = False
    assigned_agent: Optional[str] = None


class TriageAgent(BaseAgent):
    """
    AI Agent for intelligent ticket triage using Anthropic Claude.
    
    Capabilities:
    - Analyze ticket content using NLU
    - Classify tickets by category and priority
    - Retrieve relevant knowledge base articles
    - Find similar historical tickets
    - Recommend resolution path
    """
    
    AUTO_RESOLVE_THRESHOLD = 0.85
    AGENT_RESOLUTION_THRESHOLD = 0.65
    
    PRIORITY_KEYWORDS = {
        TicketPriority.CRITICAL: [
            "outage", "down", "not working for entire", "production",
            "all users affected", "security breach", "data loss"
        ],
        TicketPriority.HIGH: [
            "urgent", "asap", "blocking", "cannot work", "executive",
            "customer facing", "deadline"
        ],
        TicketPriority.MEDIUM: [
            "slow", "intermittent", "sometimes", "occasional"
        ],
        TicketPriority.LOW: [
            "question", "how to", "when possible", "enhancement",
            "nice to have", "feature request"
        ]
    }
    
    CATEGORY_PATTERNS = {
        TicketCategory.NETWORK: [
            "vpn", "wifi", "network", "internet", "connection", "dns",
            "firewall", "proxy", "bandwidth"
        ],
        TicketCategory.HARDWARE: [
            "laptop", "monitor", "keyboard", "mouse", "printer", "dock",
            "headset", "webcam", "charger"
        ],
        TicketCategory.SOFTWARE: [
            "install", "update", "crash", "error", "license", "application",
            "software", "program"
        ],
        TicketCategory.ACCESS: [
            "password", "login", "access", "permission", "unlock", "mfa",
            "authentication", "sso", "account"
        ],
        TicketCategory.EMAIL: [
            "email", "outlook", "calendar", "teams", "meeting", "mailbox",
            "distribution list"
        ]
    }
    
    def __init__(self, retriever: Optional[ContextRetriever] = None):
        super().__init__(AgentConfig(
            name="triage_agent",
            description="Intelligent ticket classification and routing",
            model="claude-sonnet-4-20250514",
            temperature=0.1,
            capabilities=[
                AgentCapability.READ_TICKET,
                AgentCapability.ACCESS_KNOWLEDGE_BASE,
                AgentCapability.UPDATE_TICKET
            ],
            require_compliance_check=False,
            requests_per_minute=50,
            tokens_per_minute=100000
        ))
        
        self.retriever = retriever or ContextRetriever()
        self._register_tools()
    
    def _register_tools(self):
        """Register tools available to the triage agent."""
        self.register_tool(
            name="search_knowledge_base",
            func=self._search_knowledge_base,
            description="Search IT knowledge base for relevant articles"
        )
        self.register_tool(
            name="find_similar_tickets",
            func=self._find_similar_tickets,
            description="Find historically similar tickets"
        )
        self.register_tool(
            name="get_user_context",
            func=self._get_user_context,
            description="Get context about the user"
        )
    
    def _get_system_prompt(self) -> str:
        return """You are an expert IT support triage agent. Your role is to:

1. ANALYZE incoming IT support tickets thoroughly
2. CLASSIFY tickets by category (Network, Hardware, Software, Access, Email, Other)
3. PRIORITIZE based on business impact and urgency
4. DETERMINE the optimal resolution path:
   - AUTO_RESOLVE: Simple, well-documented issues
   - AGENT_RESOLUTION: Issues requiring AI agent with tools
   - HUMAN_ESCALATION: Complex issues requiring human expertise
   - INFORMATION_REQUEST: Need more information from user

5. IDENTIFY relevant knowledge base articles
6. ESTIMATE resolution time

Be decisive but accurate. When uncertain, favor human escalation.

Output your analysis in this exact format:
FINAL_CATEGORY: [Network|Hardware|Software|Access|Email|Other]
FINAL_PRIORITY: [Critical|High|Medium|Low]
DECISION: [AUTO_RESOLVE|AGENT_RESOLUTION|HUMAN_ESCALATION|INFORMATION_REQUEST]
CONFIDENCE: [0.0-1.0]
RESOLUTION_PATH: [Brief description]
ESTIMATED_MINUTES: [number]
REASONING: [Your analysis]"""

    async def execute(self, context: AgentContext) -> AgentState:
        """Execute triage analysis on the ticket in context."""
        if not context.ticket_id:
            raise ValueError("Ticket ID required for triage")
        
        ticket_data = context.metadata.get("ticket_data", {})
        
        result = await self.analyze(
            ticket_id=context.ticket_id,
            title=ticket_data.get("title", ""),
            description=ticket_data.get("description", ""),
            user_email=ticket_data.get("user_email"),
            attachments=ticket_data.get("attachments", [])
        )
        
        return AgentState(
            agent_name=self.name,
            status="completed",
            output=result.model_dump(),
            actions=[AgentAction(
                action_type="triage_analysis",
                summary=f"Classified as {result.category.value} ({result.priority.value})",
                success=True
            )],
            metadata={
                "decision": result.decision.value,
                "confidence": result.confidence
            }
        )
    
    async def analyze(
        self,
        ticket_id: str,
        title: str,
        description: str,
        user_email: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> TriageResult:
        """Perform comprehensive triage analysis on a ticket."""
        logger.info("triage_started", ticket_id=ticket_id)
        
        combined_text = f"{title} {description}".lower()
        
        # Step 1: Initial rule-based classification
        initial_category = self._detect_category(combined_text)
        initial_priority = self._detect_priority(combined_text)
        
        # Step 2: Retrieve relevant context
        knowledge_results = await self._search_knowledge_base(
            query=f"{title} {description}",
            category=initial_category
        )
        
        similar_tickets = await self._find_similar_tickets(
            title=title,
            description=description,
            category=initial_category
        )
        
        # Step 3: Get user context
        user_context = None
        if user_email:
            user_context = await self._get_user_context(user_email)
        
        # Step 4: LLM-enhanced analysis with Claude
        analysis_prompt = self._build_analysis_prompt(
            title=title,
            description=description,
            initial_category=initial_category,
            initial_priority=initial_priority,
            knowledge_results=knowledge_results,
            similar_tickets=similar_tickets,
            user_context=user_context
        )
        
        context = AgentContext(
            ticket_id=ticket_id,
            retrieved_knowledge=knowledge_results
        )
        
        llm_analysis = await self.think(analysis_prompt, context)
        
        # Step 5: Parse response and build result
        final_result = self._parse_analysis(
            ticket_id=ticket_id,
            llm_analysis=llm_analysis,
            initial_category=initial_category,
            initial_priority=initial_priority,
            knowledge_results=knowledge_results,
            similar_tickets=similar_tickets,
            user_context=user_context
        )
        
        logger.info(
            "triage_completed",
            ticket_id=ticket_id,
            category=final_result.category.value,
            priority=final_result.priority.value,
            decision=final_result.decision.value,
            confidence=final_result.confidence
        )
        
        return final_result
    
    def _detect_category(self, text: str) -> TicketCategory:
        """Detect ticket category using keyword matching."""
        scores = {}
        for category, keywords in self.CATEGORY_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[category] = score
        
        if not any(scores.values()):
            return TicketCategory.OTHER
        
        return max(scores, key=scores.get)
    
    def _detect_priority(self, text: str) -> TicketPriority:
        """Detect ticket priority using keyword matching."""
        for priority in [TicketPriority.CRITICAL, TicketPriority.HIGH, 
                        TicketPriority.MEDIUM, TicketPriority.LOW]:
            keywords = self.PRIORITY_KEYWORDS.get(priority, [])
            if any(kw in text for kw in keywords):
                return priority
        
        return TicketPriority.MEDIUM
    
    async def _search_knowledge_base(
        self,
        query: str,
        category: Optional[TicketCategory] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant articles."""
        filters = {}
        if category:
            filters["category"] = category.value
        
        results = await self.retriever.retrieve(
            query=query,
            filters=filters,
            top_k=limit
        )
        
        return results
    
    async def _find_similar_tickets(
        self,
        title: str,
        description: str,
        category: Optional[TicketCategory] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Find similar historical tickets."""
        results = await self.retriever.retrieve(
            query=f"{title} {description}",
            doc_type="historical_ticket",
            top_k=limit
        )
        
        return [r for r in results if r.get("metadata", {}).get("status") == "resolved"]
    
    async def _get_user_context(self, user_email: str) -> Dict[str, Any]:
        """Get context about the user."""
        return {
            "email": user_email,
            "department": "Engineering",
            "is_vip": False,
            "recent_ticket_count": 2,
            "preferred_contact": "email"
        }
    
    def _build_analysis_prompt(
        self,
        title: str,
        description: str,
        initial_category: TicketCategory,
        initial_priority: TicketPriority,
        knowledge_results: List[Dict[str, Any]],
        similar_tickets: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for Claude."""
        prompt = f"""Analyze this IT support ticket:

TICKET:
Title: {title}
Description: {description}

INITIAL CLASSIFICATION (from rules):
- Category: {initial_category.value}
- Priority: {initial_priority.value}

RELEVANT KNOWLEDGE BASE ARTICLES:
{self._format_knowledge_results(knowledge_results)}

SIMILAR HISTORICAL TICKETS:
{self._format_similar_tickets(similar_tickets)}
"""
        if user_context:
            prompt += f"""
USER CONTEXT:
- Department: {user_context.get('department', 'Unknown')}
- VIP Status: {user_context.get('is_vip', False)}
- Recent Tickets: {user_context.get('recent_ticket_count', 0)}
"""
        
        prompt += """
Provide your analysis following the exact output format specified."""

        return prompt
    
    def _format_knowledge_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No relevant articles found."
        
        formatted = []
        for i, r in enumerate(results, 1):
            content = r.get("content", "")[:300]
            source = r.get("metadata", {}).get("source", "Unknown")
            formatted.append(f"{i}. [{source}] {content}...")
        
        return "\n".join(formatted)
    
    def _format_similar_tickets(self, tickets: List[Dict[str, Any]]) -> str:
        if not tickets:
            return "No similar tickets found."
        
        formatted = []
        for i, t in enumerate(tickets, 1):
            meta = t.get("metadata", {})
            formatted.append(
                f"{i}. {meta.get('title', 'N/A')} - "
                f"Resolution: {meta.get('resolution_summary', 'N/A')[:100]}"
            )
        
        return "\n".join(formatted)
    
    def _parse_analysis(
        self,
        ticket_id: str,
        llm_analysis: str,
        initial_category: TicketCategory,
        initial_priority: TicketPriority,
        knowledge_results: List[Dict[str, Any]],
        similar_tickets: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> TriageResult:
        """Parse Claude's analysis and build final result."""
        lines = llm_analysis.split("\n")
        parsed = {}
        
        for line in lines:
            line = line.strip()
            for key in ["FINAL_CATEGORY", "FINAL_PRIORITY", "DECISION", 
                       "CONFIDENCE", "RESOLUTION_PATH", "ESTIMATED_MINUTES", "REASONING"]:
                if line.upper().startswith(key):
                    value = line.split(":", 1)[-1].strip()
                    parsed[key.lower()] = value
        
        # Map to enums with fallbacks
        try:
            category = TicketCategory(parsed.get("final_category", "").lower())
        except ValueError:
            category = initial_category
        
        try:
            priority = TicketPriority(parsed.get("final_priority", "").lower())
        except ValueError:
            priority = initial_priority
        
        try:
            decision = TriageDecision(parsed.get("decision", "").lower())
        except ValueError:
            decision = TriageDecision.AGENT_RESOLUTION
        
        try:
            confidence = float(parsed.get("confidence", "0.7"))
        except ValueError:
            confidence = 0.7
        
        try:
            estimated_minutes = int(parsed.get("estimated_minutes", "30"))
        except ValueError:
            estimated_minutes = 30
        
        assigned_agent = None
        if decision == TriageDecision.AGENT_RESOLUTION:
            assigned_agent = self._determine_resolver_agent(category)
        
        return TriageResult(
            ticket_id=ticket_id,
            category=category,
            priority=priority,
            decision=decision,
            confidence=confidence,
            suggested_resolution_path=parsed.get("resolution_path", "Manual review required"),
            relevant_runbooks=[r.get("metadata", {}).get("source", "") for r in knowledge_results],
            similar_tickets=[t.get("metadata", {}).get("ticket_id", "") for t in similar_tickets],
            estimated_resolution_time_minutes=estimated_minutes,
            reasoning=parsed.get("reasoning", "Analysis completed"),
            requires_approval=decision == TriageDecision.HUMAN_ESCALATION,
            assigned_agent=assigned_agent
        )
    
    def _determine_resolver_agent(self, category: TicketCategory) -> str:
        """Determine which agent should handle resolution."""
        agent_mapping = {
            TicketCategory.ACCESS: "access_management_agent",
            TicketCategory.NETWORK: "network_agent",
            TicketCategory.SOFTWARE: "software_agent",
            TicketCategory.EMAIL: "email_agent",
            TicketCategory.HARDWARE: "hardware_agent",
            TicketCategory.OTHER: "resolution_agent"
        }
        return agent_mapping.get(category, "resolution_agent")