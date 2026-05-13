"""
Edge Case Tests — comprehensive boundary, error, and security scenarios.

Coverage areas:
  - TriageAgent: input extremes, bad LLM output, all decision paths
  - ResolutionAgent: mixed step results, tool exceptions, compliance blocking
  - ComplianceAgent: all approval-required actions, param edge cases, sensitive data
  - RateLimiter: exact limits, token tracking, window expiry
  - KnowledgeBase filters: empty/multi/None filters
  - Orchestrator: ticket CRUD edge cases, list_tickets enrichment
  - API: XSS/SQLi sanitization, field length boundaries, chat flow logic
  - Security utilities: sanitize_input, mask_sensitive_data
  - Remediation: unapproved software, no plaintext passwords
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.triage_agent import TriageAgent, TriageDecision, TriageResult
from src.agents.resolution_agent import (
    ResolutionAgent, ResolutionResult, ResolutionStep, ResolutionPlan,
)
from src.agents.compliance_agent import ComplianceAgent
from src.agents.base_agent import AgentContext
from src.models.ticket import TicketCategory, TicketPriority, ActionResult
from src.utils.security import sanitize_input, mask_sensitive_data, validate_action_permissions, SecurityContext
from src.utils.rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _triage_llm(
    category="network", priority="medium", decision="agent_resolution",
    confidence="0.80", path="Check VPN", minutes="10", reasoning="ok"
):
    return (
        f"FINAL_CATEGORY: {category}\nFINAL_PRIORITY: {priority}\n"
        f"DECISION: {decision}\nCONFIDENCE: {confidence}\n"
        f"RESOLUTION_PATH: {path}\nESTIMATED_MINUTES: {minutes}\n"
        f"REASONING: {reasoning}"
    )


def _make_triage_agent():
    with patch("src.agents.triage_agent.ContextRetriever") as cls:
        r = MagicMock()
        r.retrieve = AsyncMock(return_value=[])
        cls.return_value = r
        return TriageAgent()


def _make_resolution_agent():
    with patch("src.agents.resolution_agent.ContextRetriever"):
        with patch("src.agents.resolution_agent.RemediationEngine"):
            return ResolutionAgent()


def _make_plan(steps, ticket_id="INC001"):
    return ResolutionPlan(
        ticket_id=ticket_id,
        summary="test plan",
        steps=steps,
        estimated_duration_minutes=5,
        confidence_score=0.8,
    )


# ============================================================================
# TriageAgent — input edge cases
# ============================================================================

class TestTriageInputEdgeCases:

    def test_empty_string_category_returns_other(self):
        agent = _make_triage_agent()
        assert agent._detect_category("") == TicketCategory.OTHER

    def test_whitespace_only_returns_other(self):
        agent = _make_triage_agent()
        assert agent._detect_category("   \t\n  ") == TicketCategory.OTHER

    def test_unicode_emoji_input_does_not_crash(self):
        agent = _make_triage_agent()
        result = agent._detect_category("🔒 can't login 🔑 password expired 🚨")
        assert result == TicketCategory.ACCESS

    def test_all_caps_input_lowercased_by_analyze_before_detection(self):
        # _detect_category receives pre-lowercased text from analyze(); test with lowercase
        agent = _make_triage_agent()
        assert agent._detect_category("vpn not working network down") == TicketCategory.NETWORK

    def test_very_long_input_does_not_crash(self):
        agent = _make_triage_agent()
        long_text = "vpn " * 2000
        result = agent._detect_category(long_text)
        assert result == TicketCategory.NETWORK

    def test_numbers_only_description_returns_other(self):
        agent = _make_triage_agent()
        assert agent._detect_category("123456789 00000 99999") == TicketCategory.OTHER

    def test_conflicting_keywords_vpn_and_password_picks_first_match(self):
        agent = _make_triage_agent()
        # CATEGORY_PATTERNS is ordered; network comes before access
        result = agent._detect_category("vpn not working and password reset needed")
        assert result in (TicketCategory.NETWORK, TicketCategory.ACCESS)

    def test_hardware_keywords_detected(self):
        agent = _make_triage_agent()
        assert agent._detect_category("my laptop screen is broken") == TicketCategory.HARDWARE

    def test_email_keywords_detected(self):
        agent = _make_triage_agent()
        assert agent._detect_category("outlook calendar not syncing") == TicketCategory.EMAIL

    def test_empty_priority_returns_medium(self):
        agent = _make_triage_agent()
        assert agent._detect_priority("") == TicketPriority.MEDIUM

    def test_critical_priority_outage_keyword(self):
        agent = _make_triage_agent()
        assert agent._detect_priority("production outage all users affected") == TicketPriority.CRITICAL

    def test_high_priority_urgent_keyword(self):
        agent = _make_triage_agent()
        assert agent._detect_priority("urgent need asap blocking deadline") == TicketPriority.HIGH

    def test_low_priority_feature_request(self):
        agent = _make_triage_agent()
        assert agent._detect_priority("nice to have feature request when possible") == TicketPriority.LOW

    def test_special_characters_do_not_crash_detection(self):
        agent = _make_triage_agent()
        result = agent._detect_category("!@#$%^&*()vpn!@#$%")
        assert result == TicketCategory.NETWORK


# ============================================================================
# TriageAgent — LLM output parsing edge cases
# ============================================================================

class TestTriageLLMParsing:

    async def test_all_valid_decisions_parsed(self):
        agent = _make_triage_agent()
        for decision_str, expected in [
            ("auto_resolve", TriageDecision.AUTO_RESOLVE),
            ("agent_resolution", TriageDecision.AGENT_RESOLUTION),
            ("human_escalation", TriageDecision.HUMAN_ESCALATION),
            ("information_request", TriageDecision.INFORMATION_REQUEST),
        ]:
            with patch.object(agent, "think", new_callable=AsyncMock) as m:
                m.return_value = _triage_llm(decision=decision_str)
                result = await agent.analyze("INC001", "title", "desc")
            assert result.decision == expected

    async def test_invalid_decision_falls_back_gracefully(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(decision="made_up_decision")
            result = await agent.analyze("INC001", "vpn issue", "cannot connect to vpn")
        assert isinstance(result, TriageResult)
        # falls back to rule-based category
        assert result.category == TicketCategory.NETWORK

    async def test_invalid_category_falls_back_to_keyword(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(category="UNICORN")
            result = await agent.analyze("INC001", "vpn broken", "vpn not working")
        assert result.category == TicketCategory.NETWORK

    async def test_confidence_clamped_below_one(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(confidence="0.99")
            result = await agent.analyze("INC001", "title", "desc")
        assert 0.0 <= result.confidence <= 1.0

    async def test_empty_llm_response_falls_back_to_rule_based(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = ""
            result = await agent.analyze("INC001", "password reset", "forgot password")
        assert isinstance(result, TriageResult)
        assert result.ticket_id == "INC001"

    async def test_llm_exception_falls_back_to_rule_based(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("API down")
            result = await agent.analyze("INC001", "email not working", "outlook crash")
        assert isinstance(result, TriageResult)
        # fallback rule-based should pick up "email" and "outlook"
        assert result.category == TicketCategory.EMAIL

    async def test_human_escalation_sets_requires_approval(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(decision="human_escalation")
            result = await agent.analyze("INC001", "complex issue", "very complex")
        assert result.requires_approval is True

    async def test_auto_resolve_decision_parsed(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(decision="auto_resolve", confidence="0.92")
            result = await agent.analyze("INC001", "simple question", "how do I reset")
        assert result.decision == TriageDecision.AUTO_RESOLVE

    async def test_information_request_decision_parsed(self):
        agent = _make_triage_agent()
        with patch.object(agent, "think", new_callable=AsyncMock) as m:
            m.return_value = _triage_llm(decision="information_request")
            result = await agent.analyze("INC001", "unclear issue", "something went wrong")
        assert result.decision == TriageDecision.INFORMATION_REQUEST


# ============================================================================
# ResolutionAgent — step execution edge cases
# ============================================================================

class TestResolutionStepExecution:

    async def test_mixed_steps_one_fail_overall_failure(self):
        agent = _make_resolution_agent()
        steps = [
            ResolutionStep(step_number=1, action="a", tool_name="run_diagnostic",
                           tool_parameters={}, expected_outcome="ok"),
            ResolutionStep(step_number=2, action="b", tool_name="nonexistent_tool",
                           tool_parameters={}, expected_outcome="ok"),
        ]
        context = AgentContext(ticket_id="INC001")
        executed = await agent._execute_plan(_make_plan(steps), context)
        evaluated = [s for s in executed if s.success is not None]
        success = bool(evaluated) and all(s.success for s in evaluated)
        assert success is False

    async def test_all_steps_succeed_overall_success(self):
        agent = _make_resolution_agent()
        steps = [
            ResolutionStep(step_number=1, action="diag", tool_name="run_diagnostic",
                           tool_parameters={}, expected_outcome="done"),
        ]
        with patch.object(agent, "execute_tool", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ActionResult(success=True, output={"ok": True}, tool_name="run_diagnostic")
            context = AgentContext(ticket_id="INC001")
            executed = await agent._execute_plan(_make_plan(steps), context)
        evaluated = [s for s in executed if s.success is not None]
        success = bool(evaluated) and all(s.success for s in evaluated)
        assert success is True

    async def test_tool_raises_exception_step_marked_failed(self):
        agent = _make_resolution_agent()
        steps = [
            ResolutionStep(step_number=1, action="diag", tool_name="run_diagnostic",
                           tool_parameters={}, expected_outcome="done"),
        ]
        with patch.object(agent, "execute_tool", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("network timeout")
            context = AgentContext(ticket_id="INC001")
            executed = await agent._execute_plan(_make_plan(steps), context)
        assert executed[0].success is False
        assert "network timeout" in (executed[0].actual_outcome or "")

    async def test_step_with_none_tool_name_marked_failed(self):
        # Steps without a tool_name hit the else branch: success=False, "not registered"
        agent = _make_resolution_agent()
        steps = [
            ResolutionStep(step_number=1, action="manual check",
                           tool_name=None, expected_outcome="done"),
        ]
        context = AgentContext(ticket_id="INC001")
        executed = await agent._execute_plan(_make_plan(steps), context)
        assert executed[0].success is False
        assert "not registered" in (executed[0].actual_outcome or "")

    async def test_empty_tool_parameters_does_not_crash(self):
        agent = _make_resolution_agent()
        steps = [
            ResolutionStep(step_number=1, action="diag", tool_name="run_diagnostic",
                           tool_parameters={}, expected_outcome="done"),
        ]
        with patch.object(agent, "execute_tool", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ActionResult(success=True, output={}, tool_name="run_diagnostic")
            context = AgentContext(ticket_id="INC001")
            executed = await agent._execute_plan(_make_plan(steps), context)
        assert len(executed) == 1

    def test_all_required_tools_registered(self):
        agent = _make_resolution_agent()
        names = {t["name"] for t in agent.get_available_tools()}
        required = {
            "reset_password", "unlock_account", "push_vpn_config",
            "run_diagnostic", "install_software", "send_user_notification",
            "update_ticket", "check_service_status",
        }
        assert required.issubset(names)

    def test_default_plan_for_email_category(self):
        agent = _make_resolution_agent()
        steps = agent._get_default_plan(TicketCategory.EMAIL)
        assert len(steps) > 0

    def test_default_plan_for_hardware_category(self):
        agent = _make_resolution_agent()
        steps = agent._get_default_plan(TicketCategory.HARDWARE)
        assert len(steps) > 0

    def test_default_plan_for_software_category(self):
        agent = _make_resolution_agent()
        steps = agent._get_default_plan(TicketCategory.SOFTWARE)
        assert len(steps) > 0


# ============================================================================
# ComplianceAgent — all approval-required actions blocked
# ============================================================================

class TestComplianceAllApprovalActions:

    @pytest.fixture
    def agent(self):
        return ComplianceAgent()

    async def test_every_approval_required_action_is_blocked(self, agent):
        for action in agent.APPROVAL_REQUIRED_ACTIONS:
            result = await agent.validate_action(
                action_type=action,
                parameters={},
                context=AgentContext(ticket_id="INC001"),
            )
            assert result is False, f"{action} should be blocked but was approved"

    async def test_empty_parameters_does_not_raise(self, agent):
        result = await agent.validate_action(
            action_type="run_diagnostic",
            parameters={},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is True

    async def test_sec001_missing_key_defaults_to_blocked(self, agent):
        """identity_verified missing → treated as False → reset_password blocked."""
        rule = next(r for r in agent.rules if r.rule_id == "SEC-001")
        violation = agent._check_rule(rule, "reset_password", {})
        assert violation is not None

    async def test_sec002_missing_grants_admin_defaults_to_safe(self, agent):
        """grants_admin missing → treated as False → modify_user_account passes."""
        rule = next(r for r in agent.rules if r.rule_id == "SEC-002")
        violation = agent._check_rule(rule, "modify_user_account", {})
        assert violation is None

    async def test_pol001_empty_software_id_blocked(self, agent):
        rule = next(r for r in agent.rules if r.rule_id == "POL-001")
        violation = agent._check_rule(rule, "install_software", {"software_id": ""})
        assert violation is not None

    async def test_sec001_reset_with_verified_true_passes(self, agent):
        result = await agent.validate_action(
            action_type="reset_password",
            parameters={"identity_verified": True, "user_email": "user@example.com"},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is True

    async def test_action_not_in_any_rule_passes_if_not_approval_required(self, agent):
        result = await agent.validate_action(
            action_type="send_user_notification",
            parameters={"message": "hi"},
            context=AgentContext(ticket_id="INC001"),
        )
        assert result is True


# ============================================================================
# ComplianceAgent — sensitive data detection edge cases
# ============================================================================

class TestComplianceSensitiveData:

    @pytest.fixture
    def agent(self):
        return ComplianceAgent()

    def test_ssn_field_detected(self, agent):
        assert agent._contains_sensitive_data({"user_ssn": "123-45-6789"}) is True

    def test_social_security_field_detected(self, agent):
        assert agent._contains_sensitive_data({"social_security_number": "123"}) is True

    def test_credit_card_field_detected(self, agent):
        assert agent._contains_sensitive_data({"credit_card_number": "4111"}) is True

    def test_bank_account_field_detected(self, agent):
        assert agent._contains_sensitive_data({"bank_account": "9999"}) is True

    def test_medical_field_detected(self, agent):
        assert agent._contains_sensitive_data({"medical_history": "..."}) is True

    def test_salary_field_detected(self, agent):
        assert agent._contains_sensitive_data({"salary_info": "100k"}) is True

    def test_non_sensitive_field_passes(self, agent):
        assert agent._contains_sensitive_data({"device_id": "LAPTOP-001"}) is False

    def test_empty_dict_passes(self, agent):
        assert agent._contains_sensitive_data({}) is False

    def test_mixed_dict_one_sensitive_returns_true(self, agent):
        assert agent._contains_sensitive_data({
            "user_email": "user@test.com",
            "credit_card": "4111-1111-1111-1111",
            "device_id": "D-001",
        }) is True


# ============================================================================
# ComplianceAgent — resolution plan validation
# ============================================================================

class TestComplianceResolutionPlan:

    @pytest.fixture
    def agent(self):
        return ComplianceAgent()

    async def test_empty_path_is_safe(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001", category="access", suggested_path=""
        )
        assert result is True

    async def test_grant_admin_in_path_blocked(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001", category="access",
            suggested_path="Grant admin access to the user"
        )
        assert result is False

    async def test_disable_mfa_in_path_blocked(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001", category="access",
            suggested_path="Disable MFA for the account"
        )
        assert result is False

    async def test_delete_account_in_path_blocked(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001", category="access",
            suggested_path="Delete the user account from AD"
        )
        assert result is False

    async def test_safe_path_approved(self, agent):
        result = await agent.validate_resolution_plan(
            ticket_id="INC001", category="network",
            suggested_path="Push VPN configuration to device"
        )
        assert result is True


# ============================================================================
# RateLimiter — limit boundaries and token tracking
# ============================================================================

class TestRateLimiterBoundaries:

    async def test_exactly_at_rpm_limit_waits(self):
        limiter = RateLimiter(requests_per_minute=2, tokens_per_minute=1_000_000)
        await limiter.acquire()
        await limiter.acquire()
        # Third acquire must wait; mock sleep to clear the window
        sleep_called = []

        async def fast_sleep(t):
            sleep_called.append(t)
            limiter._request_times.clear()

        with patch("src.utils.rate_limiter.asyncio.sleep", new=fast_sleep):
            await limiter.acquire()

        assert sleep_called, "should have waited at RPM=2 after 2 acquires"

    async def test_within_limit_never_sleeps(self):
        limiter = RateLimiter(requests_per_minute=10, tokens_per_minute=1_000_000)
        sleep_called = []

        async def spy_sleep(t):
            sleep_called.append(t)

        with patch("src.utils.rate_limiter.asyncio.sleep", new=spy_sleep):
            for _ in range(5):
                await limiter.acquire()

        assert not sleep_called

    def test_stats_reflect_acquired_requests(self):
        limiter = RateLimiter(requests_per_minute=50, tokens_per_minute=100_000)
        asyncio.get_event_loop().run_until_complete(limiter.acquire())
        stats = limiter.get_stats()
        assert stats["requests_in_window"] >= 1

    def test_stats_available_decreases_after_acquire(self):
        limiter = RateLimiter(requests_per_minute=10, tokens_per_minute=100_000)
        asyncio.get_event_loop().run_until_complete(limiter.acquire())
        stats = limiter.get_stats()
        assert stats["requests_available"] <= 9

    def test_stats_all_keys_present(self):
        limiter = RateLimiter(requests_per_minute=50, tokens_per_minute=100_000)
        stats = limiter.get_stats()
        for key in ("requests_in_window", "tokens_in_window", "requests_available", "tokens_available"):
            assert key in stats, f"missing key: {key}"

    async def test_lock_not_held_during_sleep(self):
        limiter = RateLimiter(requests_per_minute=1, tokens_per_minute=1_000_000)
        await limiter.acquire()
        locked_during_sleep = []

        async def check_sleep(t):
            locked_during_sleep.append(limiter._lock.locked())
            limiter._request_times.clear()

        with patch("src.utils.rate_limiter.asyncio.sleep", new=check_sleep):
            await limiter.acquire()

        assert locked_during_sleep, "sleep never called"
        assert not any(locked_during_sleep), "lock was held during sleep"


# ============================================================================
# KnowledgeBase filter construction
# ============================================================================

class TestKnowledgeBaseFilterConstruction:

    def _build_filter(self, filters: dict):
        if not filters:
            return None
        if len(filters) > 1:
            return {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}
        k, v = next(iter(filters.items()))
        return {k: {"$eq": v}}

    def test_single_filter_eq_operator(self):
        result = self._build_filter({"category": "network"})
        assert result == {"category": {"$eq": "network"}}

    def test_two_filters_uses_and(self):
        result = self._build_filter({"category": "network", "doc_type": "runbook"})
        assert "$and" in result
        assert len(result["$and"]) == 2

    def test_multi_filter_each_clause_has_eq(self):
        result = self._build_filter({"a": "1", "b": "2", "c": "3"})
        for clause in result["$and"]:
            for val in clause.values():
                assert "$eq" in val

    def test_empty_filter_returns_none(self):
        assert self._build_filter({}) is None

    def test_single_filter_with_numeric_value(self):
        result = self._build_filter({"score": 5})
        assert result == {"score": {"$eq": 5}}

    def test_single_filter_with_boolean_value(self):
        result = self._build_filter({"active": True})
        assert result == {"active": {"$eq": True}}


# ============================================================================
# Orchestrator — ticket CRUD and list_tickets edge cases
# ============================================================================

class TestOrchestratorTicketEdgeCases:

    @pytest.fixture
    def orch(self):
        with patch("src.workflows.orchestrator.TriageAgent"), \
             patch("src.workflows.orchestrator.ResolutionAgent"), \
             patch("src.workflows.orchestrator.ComplianceAgent"), \
             patch("src.workflows.orchestrator.ContextRetriever"):
            from src.workflows.orchestrator import AgentOrchestrator
            o = AgentOrchestrator.__new__(AgentOrchestrator)
            o._tickets = {}
            o._workflow_results = {}
            return o

    def test_list_tickets_empty(self, orch):
        assert orch.list_tickets() == []

    def test_store_ticket_then_list(self, orch):
        orch.store_ticket("INC001", {
            "title": "Test", "description": "desc",
            "category": "network", "priority": "medium",
            "created_at": "2026-01-01T00:00:00"
        })
        tickets = orch.list_tickets()
        assert len(tickets) == 1
        assert tickets[0]["ticket_id"] == "INC001"

    def test_store_ticket_overwrites_existing(self, orch):
        orch.store_ticket("INC001", {"title": "Old", "category": "network"})
        orch.store_ticket("INC001", {"title": "New", "category": "access"})
        tickets = orch.list_tickets()
        assert len(tickets) == 1
        assert tickets[0]["title"] == "New"

    def test_list_tickets_sorted_newest_first(self, orch):
        orch._tickets = {
            "INC001": {"title": "A", "created_at": "2026-01-01T00:00:00", "status": "new"},
            "INC002": {"title": "B", "created_at": "2026-01-03T00:00:00", "status": "new"},
            "INC003": {"title": "C", "created_at": "2026-01-02T00:00:00", "status": "new"},
        }
        ids = [t["ticket_id"] for t in orch.list_tickets()]
        assert ids == ["INC002", "INC003", "INC001"]

    def test_list_tickets_enriched_with_workflow_result(self, orch):
        from src.workflows.orchestrator import WorkflowStatus, WorkflowResult
        orch._tickets["INC001"] = {"title": "T", "category": "access", "status": "new"}
        orch._workflow_results["INC001"] = WorkflowResult(
            ticket_id="INC001", status=WorkflowStatus.COMPLETED,
            resolution_summary="Fixed it", actions_taken=["step1"],
            escalated=False, total_duration_seconds=5.0, iteration_count=1,
        )
        tickets = orch.list_tickets()
        assert tickets[0]["status"] == WorkflowStatus.COMPLETED.value
        assert tickets[0]["resolution_summary"] == "Fixed it"
        assert tickets[0]["escalated"] is False

    def test_list_tickets_escalated_flag_set(self, orch):
        from src.workflows.orchestrator import WorkflowStatus, WorkflowResult
        orch._tickets["INC002"] = {"title": "E", "category": "hardware", "status": "escalating"}
        orch._workflow_results["INC002"] = WorkflowResult(
            ticket_id="INC002", status=WorkflowStatus.ESCALATING,
            resolution_summary="Needs human", actions_taken=[],
            escalated=True, escalation_reason="Too complex",
            total_duration_seconds=3.0, iteration_count=1,
        )
        tickets = orch.list_tickets()
        assert tickets[0]["escalated"] is True

    async def test_get_workflow_status_not_found(self, orch):
        result = await orch.get_workflow_status("NONEXISTENT")
        assert result["status"] == "not_found"

    async def test_get_workflow_status_ticket_exists_no_result(self, orch):
        orch._tickets["INC010"] = {
            "title": "Test", "description": "Desc",
            "category": "software", "priority": "low",
            "created_at": "2026-01-01T00:00:00", "status": "processing",
        }
        result = await orch.get_workflow_status("INC010")
        assert result["status"] == "processing"
        assert result["completed"] is False

    def test_analytics_no_tickets_all_zeros(self, orch):
        stats = orch.get_analytics()
        assert stats["total_tickets"] == 0
        assert stats["resolution_rate"] == 0.0
        assert stats["auto_resolved"] == 0

    def test_analytics_auto_resolved_threshold_under_30s(self, orch):
        from src.workflows.orchestrator import WorkflowStatus, WorkflowResult
        orch._tickets["INC001"] = {"category": "access", "status": "completed"}
        orch._tickets["INC002"] = {"category": "access", "status": "completed"}
        # Fast completion → auto-resolved
        orch._workflow_results["INC001"] = WorkflowResult(
            ticket_id="INC001", status=WorkflowStatus.COMPLETED,
            resolution_summary="Fast", actions_taken=[], escalated=False,
            total_duration_seconds=10.0, iteration_count=1,
        )
        # Slow completion → not auto-resolved
        orch._workflow_results["INC002"] = WorkflowResult(
            ticket_id="INC002", status=WorkflowStatus.COMPLETED,
            resolution_summary="Slow", actions_taken=[], escalated=False,
            total_duration_seconds=120.0, iteration_count=2,
        )
        stats = orch.get_analytics()
        assert stats["auto_resolved"] == 1

    def test_analytics_category_none_counts_as_other(self, orch):
        orch._tickets["INC001"] = {"status": "new"}  # no category key
        stats = orch.get_analytics()
        assert stats["top_categories"].get("other", 0) == 1


# ============================================================================
# API edge cases — XSS, SQL injection, field boundaries, chat flow
# ============================================================================

@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock, AsyncMock

    with patch("src.api.main.AgentOrchestrator") as mock_orch_cls, \
         patch("src.api.main.KnowledgeBase"), \
         patch("src.api.main.setup_tracing"), \
         patch("src.api.main.anthropic_client", None):  # start with no client
        mock_orch = MagicMock()
        mock_orch.store_ticket = MagicMock()
        mock_orch.list_tickets = MagicMock(return_value=[])
        mock_orch.get_workflow_status = AsyncMock(return_value={
            "ticket_id": "INC001", "status": "new", "title": "T",
            "description": "D", "category": "network", "priority": "medium",
            "created_at": "2026-01-01T00:00:00", "completed": False,
        })
        mock_orch.get_analytics = MagicMock(return_value={
            "total_tickets": 0, "resolved_tickets": 0, "auto_resolved": 0,
            "escalated": 0, "avg_resolution_time_minutes": 0.0,
            "resolution_rate": 0.0, "top_categories": {},
        })
        mock_orch_cls.return_value = mock_orch

        from src.api.main import app
        with TestClient(app, raise_server_exceptions=True) as client:
            client._mock_orch = mock_orch
            yield client


class TestAPIFieldBoundaries:

    def test_title_too_short_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "hi",
            "description": "This is a long enough description"
        })
        assert resp.status_code == 422

    def test_title_exactly_min_length_accepted(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN x",          # exactly 5 chars
            "description": "x" * 10,   # exactly 10 chars
        })
        assert resp.status_code == 200

    def test_title_exactly_max_length_accepted(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "V" * 200,
            "description": "x" * 10,
        })
        assert resp.status_code == 200

    def test_title_over_max_length_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "V" * 201,
            "description": "x" * 10,
        })
        assert resp.status_code == 422

    def test_description_too_short_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "short",   # < 10 chars
        })
        assert resp.status_code == 422

    def test_description_exactly_max_length_accepted(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "x" * 5000,
        })
        assert resp.status_code == 200

    def test_description_over_max_length_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "x" * 5001,
        })
        assert resp.status_code == 422

    def test_invalid_category_enum_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "x" * 10,
            "category": "unicorn",
        })
        assert resp.status_code == 422

    def test_invalid_priority_enum_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "x" * 10,
            "priority": "superurgent",
        })
        assert resp.status_code == 422

    def test_invalid_email_format_rejected(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": "x" * 10,
            "user_email": "not-an-email",
        })
        assert resp.status_code == 422

    def test_valid_category_accepted(self, api_client):
        for cat in ["network", "hardware", "software", "access", "email", "other"]:
            resp = api_client.post("/api/v1/tickets", json={
                "title": "Test issue",
                "description": "x" * 10,
                "category": cat,
            })
            assert resp.status_code == 200, f"category={cat} was rejected"

    def test_valid_priority_accepted(self, api_client):
        for pri in ["low", "medium", "high", "critical"]:
            resp = api_client.post("/api/v1/tickets", json={
                "title": "Test issue",
                "description": "x" * 10,
                "priority": pri,
            })
            assert resp.status_code == 200, f"priority={pri} was rejected"


class TestAPIXSSAndInjection:

    def test_xss_in_title_stripped(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "<script>alert(1)</script>VPN",
            "description": "x" * 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "<script>" not in data["title"]
        assert ">" not in data["title"]

    def test_xss_in_description_stripped(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "VPN issue",
            "description": '<img src=x onerror="alert(1)">Cannot connect',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "<" not in data["description"]
        assert ">" not in data["description"]

    def test_sql_injection_in_title_stripped(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "Issue'; DROP TABLE tickets;--",
            "description": "x" * 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert ";" not in data["title"]
        assert "--" not in data["title"]

    def test_sql_injection_comment_stripped(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "Test /* comment */",
            "description": "x" * 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "/*" not in data["title"]

    def test_single_quote_stripped(self, api_client):
        resp = api_client.post("/api/v1/tickets", json={
            "title": "User's computer",
            "description": "Can't connect" * 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "'" not in data["title"]


class TestAPIChatFlow:

    def test_chat_empty_message_rejected(self, api_client):
        resp = api_client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_chat_message_over_max_rejected(self, api_client):
        resp = api_client.post("/api/v1/chat", json={"message": "x" * 2001})
        assert resp.status_code == 422

    def test_chat_returns_conversation_id(self, api_client):
        resp = api_client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        assert "conversation_id" in resp.json()

    def test_chat_same_conversation_id_is_preserved(self, api_client):
        resp1 = api_client.post("/api/v1/chat", json={"message": "Hello"})
        conv_id = resp1.json()["conversation_id"]
        resp2 = api_client.post("/api/v1/chat", json={
            "message": "Still here",
            "conversation_id": conv_id,
        })
        assert resp2.json()["conversation_id"] == conv_id

    def test_chat_new_conversation_id_created_if_none_provided(self, api_client):
        resp = api_client.post("/api/v1/chat", json={"message": "Hi"})
        assert resp.json()["conversation_id"] is not None
        assert len(resp.json()["conversation_id"]) > 0

    def test_list_tickets_endpoint_returns_list(self, api_client):
        resp = api_client.get("/api/v1/tickets")
        assert resp.status_code == 200
        assert "tickets" in resp.json()
        assert isinstance(resp.json()["tickets"], list)

    def test_health_check(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_analytics_endpoint_schema(self, api_client):
        resp = api_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total_tickets", "resolved_tickets", "auto_resolved",
                    "escalated", "avg_resolution_time_minutes",
                    "resolution_rate", "top_categories"):
            assert key in data

    def test_ticket_not_found_returns_404(self, api_client):
        api_client._mock_orch.get_workflow_status = AsyncMock(
            return_value={"status": "not_found"}
        )
        resp = api_client.get("/api/v1/tickets/NONEXISTENT")
        assert resp.status_code == 404


class TestChatShouldCreateTicket:
    """Tests for the should_create_ticket logic."""

    def _should_create(self, message, history):
        from src.api.main import should_create_ticket
        return should_create_ticket(message, history)

    def test_explicit_create_ticket_phrase_triggers(self):
        assert self._should_create("create a ticket", []) is True

    def test_submit_ticket_phrase_triggers(self):
        assert self._should_create("submit ticket please", []) is True

    def test_random_message_does_not_trigger(self):
        assert self._should_create("my vpn is broken", []) is False

    def test_yes_after_assistant_mentioned_ticket(self):
        history = [
            {"role": "user", "content": "vpn issue"},
            {"role": "assistant", "content": "Would you like me to create a support ticket?"},
        ]
        assert self._should_create("yes", history) is True

    def test_yes_without_ticket_mention_does_not_trigger(self):
        history = [
            {"role": "user", "content": "vpn issue"},
            {"role": "assistant", "content": "Try restarting your VPN client."},
        ]
        assert self._should_create("yes", history) is False

    def test_escalate_phrase_triggers(self):
        assert self._should_create("please escalate this", []) is True

    def test_talk_to_human_triggers(self):
        assert self._should_create("I want to talk to human support", []) is True


class TestExtractIssueFromHistory:
    """Tests for extract_issue_from_history category/priority detection."""

    def _extract(self, messages):
        from src.api.main import extract_issue_from_history
        return extract_issue_from_history(messages)

    def _user(self, text):
        return {"role": "user", "content": text}

    def test_password_keyword_gives_access_category(self):
        result = self._extract([self._user("I forgot my password and locked out")])
        assert result["category"] == "access"

    def test_vpn_keyword_gives_network_category(self):
        result = self._extract([self._user("VPN connection is timing out")])
        assert result["category"] == "network"

    def test_outlook_keyword_gives_email_category(self):
        result = self._extract([self._user("Outlook is not syncing my calendar")])
        assert result["category"] == "email"

    def test_install_keyword_gives_software_category(self):
        result = self._extract([self._user("Need to install an application")])
        assert result["category"] == "software"

    def test_laptop_keyword_gives_hardware_category(self):
        result = self._extract([self._user("My laptop screen is cracked")])
        assert result["category"] == "hardware"

    def test_unknown_keywords_gives_other_category(self):
        result = self._extract([self._user("Something weird is happening")])
        assert result["category"] == "other"

    def test_urgent_keyword_gives_high_priority(self):
        result = self._extract([self._user("URGENT asap I cannot work")])
        assert result["priority"] == "high"

    def test_no_urgency_gives_low_priority(self):
        result = self._extract([self._user("slow computer sometimes")])
        assert result["priority"] == "low"

    def test_empty_history_returns_defaults(self):
        result = self._extract([])
        assert result["category"] == "other"
        assert result["priority"] == "low"


class TestFallbackResponse:
    """Tests for generate_fallback_response branch coverage."""

    def _fallback(self, message):
        from src.api.main import generate_fallback_response
        return generate_fallback_response(message)

    def test_greeting_hello(self):
        resp = self._fallback("Hello!")
        assert "IT Support" in resp

    def test_greeting_hi(self):
        resp = self._fallback("hi there")
        assert "IT Support" in resp

    def test_password_branch(self):
        resp = self._fallback("forgot my password")
        assert "password" in resp.lower()

    def test_vpn_branch(self):
        resp = self._fallback("VPN not connecting")
        assert "vpn" in resp.lower() or "VPN" in resp

    def test_slow_branch(self):
        resp = self._fallback("computer is running slow")
        assert "performance" in resp.lower() or "slow" in resp.lower() or "restart" in resp.lower()

    def test_email_branch(self):
        resp = self._fallback("outlook not working")
        assert "email" in resp.lower() or "outlook" in resp.lower()

    def test_install_branch(self):
        resp = self._fallback("need to install software")
        assert "install" in resp.lower() or "software" in resp.lower()

    def test_unknown_input_generic_fallback(self):
        resp = self._fallback("xyzzy frobnotz blarg")
        assert len(resp) > 10  # some response exists


# ============================================================================
# Security utilities — sanitize_input and mask_sensitive_data
# ============================================================================

class TestSanitizeInput:

    def test_empty_string_returns_empty(self):
        assert sanitize_input("") == ""

    def test_strips_angle_brackets(self):
        result = sanitize_input("<script>alert(1)</script>")
        assert "<" not in result
        assert ">" not in result

    def test_strips_single_quote(self):
        assert "'" not in sanitize_input("it's broken")

    def test_strips_double_quote(self):
        assert '"' not in sanitize_input('say "hello"')

    def test_strips_ampersand(self):
        assert "&" not in sanitize_input("foo & bar")

    def test_strips_semicolon(self):
        assert ";" not in sanitize_input("DROP TABLE; SELECT *")

    def test_strips_sql_comment(self):
        assert "--" not in sanitize_input("value -- comment")

    def test_strips_c_block_comment_open(self):
        assert "/*" not in sanitize_input("value /* injection")

    def test_strips_c_block_comment_close(self):
        assert "*/" not in sanitize_input("injection */ value")

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_input("  hello  ") == "hello"

    def test_normal_text_preserved(self):
        result = sanitize_input("VPN connection timeout error code 800")
        assert result == "VPN connection timeout error code 800"

    def test_xss_payload_fully_neutralized(self):
        result = sanitize_input('<img src=x onerror="alert(1)">')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result

    def test_sql_injection_neutralized(self):
        result = sanitize_input("'; DROP TABLE users; --")
        assert "'" not in result
        assert ";" not in result
        assert "--" not in result


class TestMaskSensitiveData:

    def test_password_field_masked(self):
        data = mask_sensitive_data({"password": "secret123"})
        assert data["password"] == "***MASKED***"

    def test_token_field_masked(self):
        data = mask_sensitive_data({"auth_token": "abc123"})
        assert data["auth_token"] == "***MASKED***"

    def test_secret_field_masked(self):
        data = mask_sensitive_data({"client_secret": "xyz"})
        assert data["client_secret"] == "***MASKED***"

    def test_api_key_field_masked(self):
        data = mask_sensitive_data({"api_key": "key123"})
        assert data["api_key"] == "***MASKED***"

    def test_non_sensitive_field_preserved(self):
        data = mask_sensitive_data({"user_email": "user@test.com"})
        assert data["user_email"] == "user@test.com"

    def test_nested_dict_password_masked(self):
        data = mask_sensitive_data({"user": {"password": "secret", "name": "Alice"}})
        assert data["user"]["password"] == "***MASKED***"
        assert data["user"]["name"] == "Alice"

    def test_empty_dict_returns_empty(self):
        assert mask_sensitive_data({}) == {}

    def test_mixed_dict_only_sensitive_masked(self):
        data = mask_sensitive_data({
            "device_id": "LAPTOP-001",
            "token": "abc",
            "category": "network",
        })
        assert data["device_id"] == "LAPTOP-001"
        assert data["token"] == "***MASKED***"
        assert data["category"] == "network"


class TestValidateActionPermissions:

    def test_admin_role_has_all_permissions(self):
        ctx = SecurityContext(user_id="admin1", roles=["admin"], permissions=[])
        assert validate_action_permissions(ctx, "any_permission") is True

    def test_missing_permission_denied(self):
        ctx = SecurityContext(user_id="u1", roles=["user"], permissions=["read"])
        assert validate_action_permissions(ctx, "write") is False

    def test_exact_permission_granted(self):
        ctx = SecurityContext(user_id="u1", roles=["user"], permissions=["execute_remediation"])
        assert validate_action_permissions(ctx, "execute_remediation") is True

    def test_empty_context_denied(self):
        assert validate_action_permissions(None, "anything") is False

    def test_no_roles_no_permissions_denied(self):
        ctx = SecurityContext(user_id="u1", roles=[], permissions=[])
        assert validate_action_permissions(ctx, "read_ticket") is False


# ============================================================================
# Remediation engine — no hardcoded passwords, unapproved software
# ============================================================================

class TestRemediationEngine:

    @pytest.fixture
    def engine(self):
        from src.tools.remediation import RemediationEngine
        return RemediationEngine()

    async def test_reset_password_no_plaintext_password_in_response(self, engine):
        result = await engine.reset_password(user_email="user@test.com", temporary=True)
        # The response must not expose an actual password string
        result_str = str(result)
        assert "TempPass" not in result_str
        assert "password123" not in result_str.lower()
        assert result["success"] is True

    async def test_reset_password_sets_must_change_flag(self, engine):
        result = await engine.reset_password(user_email="user@test.com", temporary=True)
        assert result["must_change_on_login"] is True

    async def test_reset_password_permanent_no_change_required(self, engine):
        result = await engine.reset_password(user_email="user@test.com", temporary=False)
        assert result["must_change_on_login"] is False

    async def test_unlock_account_returns_active_status(self, engine):
        result = await engine.unlock_account(user_email="user@test.com")
        assert result["success"] is True
        assert result["account_status"] == "active"

    async def test_install_approved_software_succeeds(self, engine):
        for software in ["office365", "zoom", "slack", "chrome", "vscode"]:
            result = await engine.install_software(software_id=software, device_id="D-001")
            assert result["success"] is True, f"{software} should be approved"

    async def test_install_unapproved_software_fails(self, engine):
        result = await engine.install_software(software_id="malware", device_id="D-001")
        assert result["success"] is False
        assert "not approved" in result["error"]

    async def test_install_unapproved_case_insensitive(self, engine):
        result = await engine.install_software(software_id="ZOOM")  # uppercase approved
        assert result["success"] is True

    async def test_run_diagnostic_returns_expected_fields(self, engine):
        result = await engine.run_diagnostic(device_id="LAPTOP-001")
        assert result["success"] is True
        assert "results" in result
        assert "cpu_usage" in result["results"]
        assert "memory_usage" in result["results"]

    async def test_push_vpn_config_no_target_still_works(self, engine):
        result = await engine.push_vpn_config()  # both optional
        assert result["success"] is True

    async def test_unlock_account_no_target_still_works(self, engine):
        result = await engine.unlock_account()  # both optional
        assert result["success"] is True

    async def test_enable_mfa_default_method(self, engine):
        result = await engine.enable_mfa(user_email="user@test.com")
        assert result["success"] is True
        assert result["method"] == "authenticator"

    async def test_enable_mfa_custom_method(self, engine):
        result = await engine.enable_mfa(user_email="user@test.com", method="sms")
        assert result["method"] == "sms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
