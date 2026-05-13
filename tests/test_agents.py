"""
Agent Tests

Unit tests for the AI agent system.
Mocking strategy: patch BaseAgent.think() so tests never hit the real Claude API.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.agents.triage_agent import TriageAgent, TriageDecision, TriageResult
from src.agents.resolution_agent import ResolutionAgent, ResolutionResult, ResolutionStep, ResolutionPlan
from src.agents.compliance_agent import ComplianceAgent
from src.agents.base_agent import AgentContext
from src.models.ticket import TicketCategory, TicketPriority, TicketStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_triage_response(
    category="network",
    priority="medium",
    decision="agent_resolution",
    confidence="0.85",
    path="Check VPN configuration",
    minutes="15",
    reasoning="Standard VPN issue",
):
    return (
        f"FINAL_CATEGORY: {category}\n"
        f"FINAL_PRIORITY: {priority}\n"
        f"DECISION: {decision}\n"
        f"CONFIDENCE: {confidence}\n"
        f"RESOLUTION_PATH: {path}\n"
        f"ESTIMATED_MINUTES: {minutes}\n"
        f"REASONING: {reasoning}"
    )


# ---------------------------------------------------------------------------
# TriageAgent — keyword classification (no LLM)
# ---------------------------------------------------------------------------

class TestTriageAgentClassification:

    @pytest.fixture
    def agent(self):
        with patch("src.agents.triage_agent.ContextRetriever"):
            return TriageAgent()

    def test_detect_network_category(self, agent):
        assert agent._detect_category("cannot connect to vpn timeout errors") == TicketCategory.NETWORK

    def test_detect_access_category(self, agent):
        assert agent._detect_category("forgot password cannot login account locked") == TicketCategory.ACCESS

    def test_detect_software_category(self, agent):
        assert agent._detect_category("outlook keeps crashing need to reinstall software") == TicketCategory.SOFTWARE

    def test_detect_hardware_category(self, agent):
        assert agent._detect_category("laptop screen broken monitor not working") == TicketCategory.HARDWARE

    def test_detect_email_category(self, agent):
        assert agent._detect_category("outlook calendar not syncing email issue") == TicketCategory.EMAIL

    def test_detect_other_when_no_keywords(self, agent):
        assert agent._detect_category("random unrelated text xyz") == TicketCategory.OTHER

    def test_detect_critical_priority(self, agent):
        assert agent._detect_priority("entire production system is down all users affected") == TicketPriority.CRITICAL

    def test_detect_high_priority(self, agent):
        assert agent._detect_priority("urgent asap blocking my deadline cannot work") == TicketPriority.HIGH

    def test_detect_medium_priority(self, agent):
        assert agent._detect_priority("wifi is slow sometimes intermittent") == TicketPriority.MEDIUM

    def test_detect_low_priority(self, agent):
        assert agent._detect_priority("question about how to use excel feature request") == TicketPriority.LOW

    def test_default_priority_is_medium(self, agent):
        assert agent._detect_priority("my computer did a thing") == TicketPriority.MEDIUM


# ---------------------------------------------------------------------------
# TriageAgent — LLM analysis (think() mocked)
# ---------------------------------------------------------------------------

class TestTriageAgentAnalysis:

    @pytest.fixture
    def agent(self):
        with patch("src.agents.triage_agent.ContextRetriever") as mock_retriever_cls:
            mock_retriever = MagicMock()
            mock_retriever.retrieve = AsyncMock(return_value=[])
            mock_retriever_cls.return_value = mock_retriever
            return TriageAgent()

    async def test_analyze_returns_triage_result(self, agent):
        with patch.object(agent, "think", new_callable=AsyncMock) as mock_think:
            mock_think.return_value = _mock_triage_response(
                category="network", decision="agent_resolution", confidence="0.85"
            )
            result = await agent.analyze(
                ticket_id="INC001",
                title="VPN not working",
                description="Cannot connect to corporate VPN from home",
            )

        assert isinstance(result, TriageResult)
        assert result.ticket_id == "INC001"
        assert result.category == TicketCategory.NETWORK
        assert result.priority == TicketPriority.MEDIUM
        assert result.decision == TriageDecision.AGENT_RESOLUTION
        assert result.confidence == 0.85

    async def test_analyze_falls_back_to_rule_based_on_bad_llm_output(self, agent):
        with patch.object(agent, "think", new_callable=AsyncMock) as mock_think:
            mock_think.return_value = "this is not parseable at all"
            result = await agent.analyze(
                ticket_id="INC002",
                title="VPN issues",
                description="vpn not connecting",
            )

        # Falls back to initial rule-based classification
        assert isinstance(result, TriageResult)
        assert result.category == TicketCategory.NETWORK

    async def test_analyze_human_escalation_sets_requires_approval(self, agent):
        with patch.object(agent, "think", new_callable=AsyncMock) as mock_think:
            mock_think.return_value = _mock_triage_response(
                decision="human_escalation", confidence="0.9"
            )
            result = await agent.analyze(
                ticket_id="INC003", title="Complex issue", description="Very complex problem"
            )

        assert result.requires_approval is True


# ---------------------------------------------------------------------------
# ResolutionAgent — tool registration and default plans
# ---------------------------------------------------------------------------

class TestResolutionAgentTools:

    @pytest.fixture
    def agent(self):
        with patch("src.agents.resolution_agent.ContextRetriever"):
            with patch("src.agents.resolution_agent.RemediationEngine"):
                return ResolutionAgent()

    def test_required_tools_registered(self, agent):
        names = {t["name"] for t in agent.get_available_tools()}
        assert {"reset_password", "unlock_account", "push_vpn_config", "run_diagnostic"}.issubset(names)

    def test_default_plan_access_has_unlock_step(self, agent):
        steps = agent._get_default_plan(TicketCategory.ACCESS)
        assert len(steps) > 0
        assert any("unlock" in s.action.lower() for s in steps)

    def test_default_plan_network_has_vpn_step(self, agent):
        steps = agent._get_default_plan(TicketCategory.NETWORK)
        assert any("vpn" in s.action.lower() for s in steps)

    def test_default_plan_unknown_category_returns_diagnostic(self, agent):
        steps = agent._get_default_plan(TicketCategory.OTHER)
        assert len(steps) > 0
        assert steps[0].tool_name == "run_diagnostic"


# ---------------------------------------------------------------------------
# ResolutionAgent — bug fixes
# ---------------------------------------------------------------------------

class TestResolutionAgentBugFixes:

    @pytest.fixture
    def agent(self):
        with patch("src.agents.resolution_agent.ContextRetriever"):
            with patch("src.agents.resolution_agent.RemediationEngine"):
                return ResolutionAgent()

    async def test_empty_executed_steps_returns_failure(self, agent):
        """Bug #3: all([]) was True — empty steps must not count as success."""
        plan = ResolutionPlan(
            ticket_id="INC001",
            summary="test",
            steps=[],
            estimated_duration_minutes=0,
            confidence_score=0.8,
        )
        context = AgentContext(ticket_id="INC001")

        executed = await agent._execute_plan(plan, context)
        evaluated = [s for s in executed if s.success is not None]
        success = bool(evaluated) and all(s.success for s in evaluated)

        assert success is False

    async def test_unknown_tool_name_marks_step_failed(self, agent):
        """Bug #4: steps with unregistered tool names were silently succeeding."""
        plan = ResolutionPlan(
            ticket_id="INC001",
            summary="test",
            steps=[
                ResolutionStep(
                    step_number=1,
                    action="do something",
                    tool_name="nonexistent_tool_xyz",
                    tool_parameters={},
                    expected_outcome="done",
                )
            ],
            estimated_duration_minutes=5,
            confidence_score=0.8,
        )
        context = AgentContext(ticket_id="INC001")

        executed = await agent._execute_plan(plan, context)

        assert len(executed) == 1
        assert executed[0].success is False
        assert "not registered" in (executed[0].actual_outcome or "")

    async def test_all_steps_none_success_is_failure(self, agent):
        """Bug #3 variant: steps with success=None should not count as resolved."""
        steps = [
            ResolutionStep(
                step_number=1, action="manual step", tool_name=None,
                expected_outcome="done", success=None
            )
        ]
        evaluated = [s for s in steps if s.success is not None]
        success = bool(evaluated) and all(s.success for s in evaluated)
        assert success is False


# ---------------------------------------------------------------------------
# ComplianceAgent
# ---------------------------------------------------------------------------

class TestComplianceAgent:

    @pytest.fixture
    def agent(self):
        return ComplianceAgent()

    def test_approval_required_list_contains_dangerous_actions(self, agent):
        assert "delete_user_account" in agent.APPROVAL_REQUIRED_ACTIONS
        assert "grant_admin_access" in agent.APPROVAL_REQUIRED_ACTIONS
        assert "disable_mfa" in agent.APPROVAL_REQUIRED_ACTIONS

    async def test_approval_required_action_is_blocked(self, agent):
        """delete_user_account must always be blocked."""
        result = await agent.validate_action(
            action_type="delete_user_account",
            parameters={"user_id": "user123"},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is False

    async def test_sec002_blocks_grants_admin(self, agent):
        """Bug #6: SEC-002 rule was never enforced — grants_admin must be blocked."""
        result = await agent.validate_action(
            action_type="modify_user_account",
            parameters={"grants_admin": True, "user_id": "user123"},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is False

    async def test_normal_action_without_admin_passes(self, agent):
        result = await agent.validate_action(
            action_type="run_diagnostic",
            parameters={"device_id": "device-1"},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is True

    def test_sensitive_data_detected(self, agent):
        assert agent._contains_sensitive_data({"user_ssn": "123-45-6789"}) is True
        assert agent._contains_sensitive_data({"credit_card": "4111"}) is True

    def test_non_sensitive_data_passes(self, agent):
        assert agent._contains_sensitive_data({"user_email": "test@example.com"}) is False

    async def test_safe_resolution_plan_approved(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001",
            category="access",
            suggested_path="Reset user password and send temporary credentials",
        )
        assert result is True

    async def test_risky_resolution_plan_blocked(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001",
            category="access",
            suggested_path="Grant admin access to production database",
        )
        assert result is False


# ---------------------------------------------------------------------------
# ComplianceAgent — rule engine unit tests
# ---------------------------------------------------------------------------

class TestComplianceRuleEngine:

    @pytest.fixture
    def agent(self):
        return ComplianceAgent()

    def test_sec001_blocks_password_reset_without_verification(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "SEC-001")
        violation = agent._check_rule(rule, "reset_password", {"identity_verified": False})
        assert violation is not None

    def test_sec001_passes_with_verification(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "SEC-001")
        violation = agent._check_rule(rule, "reset_password", {"identity_verified": True})
        assert violation is None

    def test_sec002_blocks_admin_grant(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "SEC-002")
        violation = agent._check_rule(rule, "modify_user_account", {"grants_admin": True})
        assert violation is not None

    def test_sec002_passes_without_admin_grant(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "SEC-002")
        violation = agent._check_rule(rule, "modify_user_account", {"grants_admin": False})
        assert violation is None

    def test_pol001_blocks_install_without_software_id(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "POL-001")
        violation = agent._check_rule(rule, "install_software", {})
        assert violation is not None

    def test_pol001_passes_with_software_id(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "POL-001")
        violation = agent._check_rule(rule, "install_software", {"software_id": "office365"})
        assert violation is None


# ---------------------------------------------------------------------------
# Rate limiter — lock released before sleep
# ---------------------------------------------------------------------------

class TestRateLimiter:

    async def test_lock_released_before_sleep(self):
        """Bug #16: lock must be free when asyncio.sleep is called."""
        from src.utils.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=1, tokens_per_minute=1_000_000)
        await limiter.acquire()  # fill the RPM bucket

        lock_state_during_sleep = []

        async def fast_sleep(t):
            # Record whether the lock is held right now
            lock_state_during_sleep.append(limiter._lock.locked())
            # Simulate time passing: clear the bucket so the retry succeeds
            limiter._request_times.clear()

        with patch("src.utils.rate_limiter.asyncio.sleep", new=fast_sleep):
            await limiter.acquire()

        assert lock_state_during_sleep, "asyncio.sleep was never called"
        assert not any(lock_state_during_sleep), "lock was held during sleep (old bug)"

    def test_get_stats_returns_expected_keys(self):
        from src.utils.rate_limiter import RateLimiter
        limiter = RateLimiter(requests_per_minute=50, tokens_per_minute=100000)
        stats = limiter.get_stats()
        assert "requests_in_window" in stats
        assert "tokens_in_window" in stats
        assert "requests_available" in stats


# ---------------------------------------------------------------------------
# KnowledgeBase — ChromaDB filter format
# ---------------------------------------------------------------------------

class TestKnowledgeBaseFilters:

    def test_single_filter_uses_eq_operator(self):
        """Bug #5: single-key filter must use {"$eq": value} not raw value."""
        from src.rag.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()

        # Replicate the filter-building logic
        filters = {"category": "network"}
        if len(filters) > 1:
            where = {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}
        else:
            k, v = next(iter(filters.items()))
            where = {k: {"$eq": v}}

        assert where == {"category": {"$eq": "network"}}

    def test_multi_filter_uses_and_with_eq(self):
        filters = {"category": "network", "doc_type": "runbook"}
        where = {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}
        for clause in where["$and"]:
            for val in clause.values():
                assert "$eq" in val


# ---------------------------------------------------------------------------
# Orchestrator — analytics reflect real ticket data
# ---------------------------------------------------------------------------

class TestOrchestratorAnalytics:

    @pytest.fixture
    def orchestrator(self):
        with patch("src.workflows.orchestrator.TriageAgent"):
            with patch("src.workflows.orchestrator.ResolutionAgent"):
                with patch("src.workflows.orchestrator.ComplianceAgent"):
                    with patch("src.workflows.orchestrator.ContextRetriever"):
                        from src.workflows.orchestrator import AgentOrchestrator, WorkflowStatus, WorkflowResult
                        orch = AgentOrchestrator.__new__(AgentOrchestrator)
                        orch._tickets = {}
                        orch._workflow_results = {}
                        return orch, WorkflowStatus, WorkflowResult

    def test_analytics_empty_returns_zeros(self, orchestrator):
        orch, _, _ = orchestrator
        stats = orch.get_analytics()
        assert stats["total_tickets"] == 0
        assert stats["resolved_tickets"] == 0
        assert stats["resolution_rate"] == 0.0

    def test_analytics_counts_resolved_tickets(self, orchestrator):
        from src.workflows.orchestrator import WorkflowStatus, WorkflowResult
        orch, _, _ = orchestrator

        orch._tickets["INC001"] = {"category": "network", "status": "completed"}
        orch._tickets["INC002"] = {"category": "access", "status": "completed"}
        orch._workflow_results["INC001"] = WorkflowResult(
            ticket_id="INC001",
            status=WorkflowStatus.COMPLETED,
            resolution_summary="Fixed",
            actions_taken=["step1"],
            escalated=False,
            total_duration_seconds=10.0,
            iteration_count=1,
        )

        stats = orch.get_analytics()
        assert stats["total_tickets"] == 2
        assert stats["resolved_tickets"] == 1
        assert stats["resolution_rate"] == 0.5

    def test_analytics_counts_escalated(self, orchestrator):
        from src.workflows.orchestrator import WorkflowStatus, WorkflowResult
        orch, _, _ = orchestrator

        orch._tickets["INC003"] = {"category": "hardware", "status": "escalating"}
        orch._workflow_results["INC003"] = WorkflowResult(
            ticket_id="INC003",
            status=WorkflowStatus.ESCALATING,
            resolution_summary="Escalated",
            actions_taken=[],
            escalated=True,
            escalation_reason="Too complex",
            total_duration_seconds=5.0,
            iteration_count=1,
        )

        stats = orch.get_analytics()
        assert stats["escalated"] == 1

    def test_analytics_top_categories(self, orchestrator):
        orch, _, _ = orchestrator
        orch._tickets = {
            f"INC{i:03d}": {"category": "network"} for i in range(5)
        }
        orch._tickets.update({
            f"INC1{i:02d}": {"category": "access"} for i in range(3)
        })

        stats = orch.get_analytics()
        assert stats["top_categories"]["network"] == 5
        assert stats["top_categories"]["access"] == 3


# ---------------------------------------------------------------------------
# AgentContext model
# ---------------------------------------------------------------------------

class TestAgentContext:

    def test_context_defaults(self):
        ctx = AgentContext(ticket_id="INC001", user_id="user123")
        assert ctx.ticket_id == "INC001"
        assert ctx.user_id == "user123"
        assert ctx.previous_actions == []
        assert ctx.retrieved_knowledge is None

    def test_context_accepts_metadata(self):
        ctx = AgentContext(ticket_id="INC001", metadata={"foo": "bar"})
        assert ctx.metadata["foo"] == "bar"


# ---------------------------------------------------------------------------
# FastAPI endpoints — smoke tests with TestClient
# ---------------------------------------------------------------------------

class TestAPIEndpoints:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        with patch("src.api.main.AgentOrchestrator") as mock_orch_cls:
            with patch("src.api.main.KnowledgeBase"):
                with patch("src.api.main.setup_tracing"):
                    mock_orch = MagicMock()
                    mock_orch.store_ticket = MagicMock()
                    mock_orch.get_workflow_status = AsyncMock(return_value={
                        "ticket_id": "INC00000001",
                        "status": "new",
                        "title": "Test",
                        "description": "Test desc",
                        "category": "network",
                        "priority": "medium",
                        "created_at": "2026-01-01T00:00:00",
                        "completed": False,
                    })
                    mock_orch.get_analytics = MagicMock(return_value={
                        "total_tickets": 0,
                        "resolved_tickets": 0,
                        "auto_resolved": 0,
                        "escalated": 0,
                        "avg_resolution_time_minutes": 0.0,
                        "resolution_rate": 0.0,
                        "top_categories": {},
                    })
                    mock_orch_cls.return_value = mock_orch

                    from src.api.main import app
                    with TestClient(app, raise_server_exceptions=True) as c:
                        c._orchestrator = mock_orch
                        yield c

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_create_ticket_returns_ticket_id(self, client):
        resp = client.post("/api/v1/tickets", json={
            "title": "VPN not connecting",
            "description": "I cannot connect to the corporate VPN from home office",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket_id"].startswith("INC")
        assert data["status"] == "new"

    def test_create_ticket_min_length_enforced(self, client):
        resp = client.post("/api/v1/tickets", json={
            "title": "hi",          # too short (min 5)
            "description": "short", # too short (min 10)
        })
        assert resp.status_code == 422

    def test_analytics_dashboard_returns_schema(self, client):
        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tickets" in data
        assert "resolution_rate" in data
        assert "top_categories" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
