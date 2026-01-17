"""
Agent Tests

Unit tests for the AI agent system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.agents.triage_agent import TriageAgent, TriageDecision, TriageResult
from src.agents.resolution_agent import ResolutionAgent, ResolutionResult
from src.agents.compliance_agent import ComplianceAgent
from src.agents.base_agent import AgentContext
from src.models.ticket import TicketCategory, TicketPriority


class TestTriageAgent:
    """Tests for the Triage Agent."""
    
    @pytest.fixture
    def triage_agent(self):
        """Create a triage agent for testing."""
        with patch('src.agents.triage_agent.ContextRetriever'):
            agent = TriageAgent()
            agent._llm = MagicMock()
            return agent
    
    def test_detect_category_network(self, triage_agent):
        """Test network category detection."""
        text = "cannot connect to vpn getting timeout errors"
        category = triage_agent._detect_category(text)
        assert category == TicketCategory.NETWORK
    
    def test_detect_category_access(self, triage_agent):
        """Test access category detection."""
        text = "forgot password cannot login to my account"
        category = triage_agent._detect_category(text)
        assert category == TicketCategory.ACCESS
    
    def test_detect_category_software(self, triage_agent):
        """Test software category detection."""
        text = "outlook keeps crashing need to reinstall"
        category = triage_agent._detect_category(text)
        assert category == TicketCategory.SOFTWARE
    
    def test_detect_priority_critical(self, triage_agent):
        """Test critical priority detection."""
        text = "entire production system is down affecting all users"
        priority = triage_agent._detect_priority(text)
        assert priority == TicketPriority.CRITICAL
    
    def test_detect_priority_high(self, triage_agent):
        """Test high priority detection."""
        text = "urgent cannot work this is blocking my deadline"
        priority = triage_agent._detect_priority(text)
        assert priority == TicketPriority.HIGH
    
    def test_detect_priority_low(self, triage_agent):
        """Test low priority detection."""
        text = "question about how to use excel feature request"
        priority = triage_agent._detect_priority(text)
        assert priority == TicketPriority.LOW
    
    @pytest.mark.asyncio
    async def test_analyze_returns_triage_result(self, triage_agent):
        """Test that analyze returns a TriageResult."""
        # Mock retriever and LLM
        triage_agent.retriever = MagicMock()
        triage_agent.retriever.retrieve = AsyncMock(return_value=[])
        triage_agent._llm.ainvoke = AsyncMock(return_value=MagicMock(
            content="""FINAL_CATEGORY: network
FINAL_PRIORITY: medium
DECISION: agent_resolution
CONFIDENCE: 0.85
RESOLUTION_PATH: Check VPN configuration
ESTIMATED_MINUTES: 15
REASONING: Standard VPN issue"""
        ))
        
        result = await triage_agent.analyze(
            ticket_id="INC001",
            title="VPN not working",
            description="Cannot connect to corporate VPN"
        )
        
        assert isinstance(result, TriageResult)
        assert result.ticket_id == "INC001"
        assert result.category == TicketCategory.NETWORK


class TestResolutionAgent:
    """Tests for the Resolution Agent."""
    
    @pytest.fixture
    def resolution_agent(self):
        """Create a resolution agent for testing."""
        with patch('src.agents.resolution_agent.ContextRetriever'):
            with patch('src.agents.resolution_agent.RemediationEngine'):
                agent = ResolutionAgent()
                agent._llm = MagicMock()
                return agent
    
    def test_has_required_tools(self, resolution_agent):
        """Test that resolution agent has required tools."""
        tools = resolution_agent.get_available_tools()
        tool_names = [t["name"] for t in tools]
        
        assert "reset_password" in tool_names
        assert "unlock_account" in tool_names
        assert "push_vpn_config" in tool_names
    
    def test_get_default_plan_access(self, resolution_agent):
        """Test default plan for access issues."""
        plan = resolution_agent._get_default_plan(TicketCategory.ACCESS)
        
        assert len(plan) > 0
        assert any("unlock" in step.action.lower() for step in plan)


class TestComplianceAgent:
    """Tests for the Compliance Agent."""
    
    @pytest.fixture
    def compliance_agent(self):
        """Create a compliance agent for testing."""
        agent = ComplianceAgent()
        return agent
    
    def test_approval_required_actions(self, compliance_agent):
        """Test that certain actions require approval."""
        assert "delete_user_account" in compliance_agent.APPROVAL_REQUIRED_ACTIONS
        assert "grant_admin_access" in compliance_agent.APPROVAL_REQUIRED_ACTIONS
    
    @pytest.mark.asyncio
    async def test_validate_action_blocks_dangerous(self, compliance_agent):
        """Test that dangerous actions are blocked."""
        context = AgentContext(ticket_id="INC001")
        
        is_compliant = await compliance_agent.validate_action(
            action_type="delete_user_account",
            parameters={"user_id": "user123"},
            context=context
        )
        
        assert is_compliant is False
    
    def test_contains_sensitive_data(self, compliance_agent):
        """Test sensitive data detection."""
        sensitive_params = {"user_ssn": "123-45-6789"}
        normal_params = {"user_email": "test@example.com"}
        
        assert compliance_agent._contains_sensitive_data(sensitive_params) is True
        assert compliance_agent._contains_sensitive_data(normal_params) is False
    
    @pytest.mark.asyncio
    async def test_validate_resolution_plan_approves_safe(self, compliance_agent):
        """Test that safe resolution plans are approved."""
        is_approved = await compliance_agent.validate_resolution_plan(
            ticket_id="INC001",
            category="access",
            suggested_path="Reset user password and send temporary credentials"
        )
        
        assert is_approved is True
    
    @pytest.mark.asyncio
    async def test_validate_resolution_plan_blocks_risky(self, compliance_agent):
        """Test that risky resolution plans are blocked."""
        is_approved = await compliance_agent.validate_resolution_plan(
            ticket_id="INC001",
            category="access",
            suggested_path="Grant admin access to production database"
        )
        
        assert is_approved is False


class TestAgentContext:
    """Tests for AgentContext."""
    
    def test_context_creation(self):
        """Test context can be created with required fields."""
        context = AgentContext(
            ticket_id="INC001",
            user_id="user123"
        )
        
        assert context.ticket_id == "INC001"
        assert context.user_id == "user123"
        assert context.previous_actions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
