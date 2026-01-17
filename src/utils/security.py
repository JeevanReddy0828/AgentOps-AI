"""
Security Utilities Module

Security helpers for authentication, authorization, and audit logging.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel


class SecurityContext(BaseModel):
    """Security context for request/action validation."""
    user_id: str
    roles: list[str] = []
    permissions: list[str] = []
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = datetime.utcnow()


def validate_action_permissions(
    context: SecurityContext,
    required_permission: str
) -> bool:
    """Validate if context has required permission."""
    if not context:
        return False
    
    # Admin role has all permissions
    if "admin" in context.roles:
        return True
    
    return required_permission in context.permissions


def sanitize_input(value: str) -> str:
    """Sanitize user input."""
    if not value:
        return ""
    
    # Remove potentially dangerous characters
    dangerous = ["<", ">", "&", '"', "'", ";", "--", "/*", "*/"]
    result = value
    for char in dangerous:
        result = result.replace(char, "")
    
    return result.strip()


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in data."""
    sensitive_fields = ["password", "secret", "token", "key", "ssn", "credit_card"]
    
    masked = {}
    for key, value in data.items():
        if any(sf in key.lower() for sf in sensitive_fields):
            masked[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value)
        else:
            masked[key] = value
    
    return masked
