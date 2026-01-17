"""
Compliance Agent Module - Anthropic Claude Version

Security and compliance validation using Claude.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from pydantic import BaseModel, Field

from src.agents.base_agent import (
    BaseAgent, AgentConfig, AgentContext, AgentCapability
)
from src.models.agent_state import AgentState, AgentAction


logger = structlog.get_logger(__name__)


class ComplianceRule(BaseModel):
    """A compliance rule definition."""
    rule_id: str
    name: str
    description: str
    severity: str
    category: str
    conditions: Dict[str, Any]
    action_on_violation: str


class ComplianceCheckResult(BaseModel):
    """Result of a compliance check."""
    compliant: bool
    rules_checked: int
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComplianceAgent(BaseAgent):
    """
    AI Agent for security and compliance validation using Claude.
    
    Validates all automated actions against:
    - Security policies (zero-trust, least privilege)
    - Privacy requirements
    - IT policies
    - Regulatory compliance
    """
    
    APPROVAL_REQUIRED_ACTIONS = [
        "delete_user_account",
        "grant_admin_access",
        "modify_security_group",
        "export_user_data",
        "disable_mfa",
        "access_privileged_system"
    ]
    
    RESTRICTED_ACTIONS = {
        "install_software": ["software_id_required", "authorized_software_only"],
        "reset_password": ["identity_verification_required"],
        "modify_user_account": ["audit_logging_required"],
        "access_sensitive_data": ["data_classification_check"]
    }
    
    SENSITIVE_PATTERNS = [
        "ssn", "social_security", "credit_card", "bank_account",
        "medical", "health", "salary", "compensation"
    ]
    
    def __init__(self):
        super().__init__(AgentConfig(
            name="compliance_agent",
            description="Security and compliance validation",
            model="claude-sonnet-4-20250514",
            temperature=0.0,  # Deterministic for compliance
            capabilities=[
                AgentCapability.READ_TICKET,
                AgentCapability.ACCESS_KNOWLEDGE_BASE
            ],
            require_compliance_check=False,
            requests_per_minute=60,
            tokens_per_minute=50000
        ))
        
        self._load_compliance_rules()
    
    def _load_compliance_rules(self):
        """Load compliance rules."""
        self.rules = [
            ComplianceRule(
                rule_id="SEC-001",
                name="Password Reset Verification",
                description="Password resets require identity verification",
                severity="high",
                category="security",
                conditions={"action_type": "reset_password"},
                action_on_violation="block"
            ),
            ComplianceRule(
                rule_id="SEC-002",
                name="Admin Access Approval",
                description="Administrative access requires manager approval",
                severity="critical",
                category="security",
                conditions={"grants_admin": True},
                action_on_violation="block"
            ),
            ComplianceRule(
                rule_id="PRV-001",
                name="Sensitive Data Access",
                description="Access to sensitive data requires justification",
                severity="high",
                category="privacy",
                conditions={"accesses_sensitive_data": True},
                action_on_violation="warn"
            ),
            ComplianceRule(
                rule_id="POL-001",
                name="Software Installation Policy",
                description="Only authorized software can be installed",
                severity="medium",
                category="policy",
                conditions={"action_type": "install_software"},
                action_on_violation="block"
            )
        ]
    
    def _get_system_prompt(self) -> str:
        return """You are a security and compliance validation agent. Your role is to:

1. VALIDATE all automated actions against security policies
2. CHECK for potential privacy violations
3. ENSURE compliance with IT and regulatory requirements
4. IDENTIFY actions that require human approval

Security Principles:
- Zero Trust: Verify every action
- Least Privilege: Minimum necessary permissions
- Defense in Depth: Multiple validation layers
- Audit Trail: Log everything

Evaluate actions for:
1. Does this follow least privilege?
2. Is identity verification in place?
3. Are there sensitive data implications?
4. Does this require change management?
5. Any regulatory compliance issues?

Output format:
COMPLIANT: [yes/no]
RISK_LEVEL: [critical/high/medium/low]
VIOLATIONS: [list any policy violations]
RECOMMENDATIONS: [security recommendations]
REQUIRES_APPROVAL: [yes/no]"""

    async def execute(self, context: AgentContext) -> AgentState:
        """Execute compliance validation."""
        action_data = context.metadata.get("action_data", {})
        
        result = await self.validate_action(
            action_type=action_data.get("action_type", ""),
            parameters=action_data.get("parameters", {}),
            context=context
        )
        
        return AgentState(
            agent_name=self.name,
            status="completed",
            output={"compliant": result},
            actions=[AgentAction(
                action_type="compliance_check",
                summary=f"Compliance check: {'Passed' if result else 'Failed'}",
                success=True
            )]
        )
    
    async def validate_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: AgentContext
    ) -> bool:
        """Validate if an action is compliant."""
        logger.info("compliance_check_started", action_type=action_type, ticket_id=context.ticket_id)
        
        # Check if action requires approval
        if action_type in self.APPROVAL_REQUIRED_ACTIONS:
            logger.warning("action_requires_approval", action_type=action_type)
            return False
        
        # Run rule-based checks
        violations = []
        
        for rule in self.rules:
            if self._rule_applies(rule, action_type, parameters):
                violation = self._check_rule(rule, action_type, parameters)
                if violation:
                    violations.append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "severity": rule.severity
                    })
        
        # Check for sensitive data
        if self._contains_sensitive_data(parameters):
            violations.append({
                "rule_id": "PRV-002",
                "name": "Sensitive Data Detected",
                "severity": "high"
            })
        
        # LLM analysis for complex cases
        if not violations and context.metadata.get("require_llm_check", False):
            llm_result = await self._llm_compliance_check(action_type, parameters, context)
            if not llm_result.get("compliant", True):
                violations.extend(llm_result.get("violations", []))
        
        is_compliant = len([v for v in violations if v["severity"] in ["critical", "high"]]) == 0
        
        logger.info(
            "compliance_check_completed",
            action_type=action_type,
            compliant=is_compliant,
            violations=len(violations)
        )
        
        return is_compliant
    
    async def validate_resolution_plan(
        self,
        ticket_id: str,
        category: str,
        suggested_path: str
    ) -> bool:
        """Validate a resolution plan before execution."""
        high_risk_keywords = [
            "admin", "delete", "remove", "disable", "production",
            "database", "root", "sudo", "privileged"
        ]
        
        suggested_lower = suggested_path.lower()
        
        for keyword in high_risk_keywords:
            if keyword in suggested_lower:
                logger.warning("high_risk_resolution_plan", ticket_id=ticket_id, keyword=keyword)
                return False
        
        return True
    
    def _rule_applies(self, rule: ComplianceRule, action_type: str, parameters: Dict[str, Any]) -> bool:
        """Check if a rule applies to this action."""
        conditions = rule.conditions
        
        if "action_type" in conditions:
            if conditions["action_type"] != action_type:
                return False
        
        return True
    
    def _check_rule(self, rule: ComplianceRule, action_type: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if action violates a rule."""
        if rule.rule_id == "SEC-001":
            if not parameters.get("identity_verified", False):
                return {"reason": "Identity not verified"}
        
        if rule.rule_id == "POL-001":
            software_id = parameters.get("software_id")
            if not software_id:
                return {"reason": "Software ID required"}
        
        return None
    
    def _contains_sensitive_data(self, parameters: Dict[str, Any]) -> bool:
        """Check if parameters contain sensitive data."""
        params_str = str(parameters).lower()
        
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in params_str:
                return True
        
        return False
    
    async def _llm_compliance_check(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Use Claude for complex compliance analysis."""
        prompt = f"""Analyze this action for security and compliance:

ACTION: {action_type}
PARAMETERS: {parameters}
TICKET_ID: {context.ticket_id}

Evaluate against security policies and provide your analysis."""

        response = await self.think(prompt, context)
        
        compliant = "COMPLIANT: yes" in response.upper()
        violations = []
        
        if "VIOLATIONS:" in response.upper():
            violations_text = response.split("VIOLATIONS:")[-1].split("\n")[0]
            if violations_text.strip() and violations_text.strip().lower() != "none":
                violations.append({
                    "rule_id": "LLM-001",
                    "name": "LLM Analysis",
                    "severity": "medium",
                    "details": violations_text.strip()
                })
        
        return {"compliant": compliant, "violations": violations}
    
    async def audit_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        context: AgentContext
    ) -> None:
        """Record action in audit log."""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action_type,
            "ticket_id": context.ticket_id,
            "user_id": context.user_id,
            "parameters": parameters,
            "result": result,
            "agent": self.name
        }
        
        logger.info("audit_log", **audit_entry)