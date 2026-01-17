"""
Authentication Middleware

JWT-based authentication for API endpoints.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """Authenticated user model."""
    user_id: str
    email: str
    roles: list[str] = []
    permissions: list[str] = []


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """Extract and validate current user from JWT token."""
    # In production, validate JWT token
    # For now, return a mock user for development
    
    return User(
        user_id="dev-user-001",
        email="developer@company.com",
        roles=["user", "it_support"],
        permissions=["read_ticket", "create_ticket", "resolve_ticket"]
    )


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role for endpoint."""
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return user
