"""
Rate Limiter Module

Token bucket rate limiter for Anthropic API calls.
Handles both request rate limiting and token rate limiting.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from collections import deque
import structlog

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Async rate limiter for API calls with token tracking.
    
    Implements a sliding window rate limiter that tracks:
    - Requests per minute (RPM)
    - Tokens per minute (TPM)
    
    Example:
        limiter = RateLimiter(requests_per_minute=50, tokens_per_minute=100000)
        
        async def make_api_call():
            await limiter.acquire()  # Waits if rate limited
            response = await api.call()
            limiter.record_tokens(response.usage.total_tokens)
    """
    
    def __init__(
        self,
        requests_per_minute: int = 50,
        tokens_per_minute: int = 100000,
        max_wait_seconds: float = 60.0
    ):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.max_wait_seconds = max_wait_seconds
        
        # Sliding window tracking
        self._request_times: deque = deque()
        self._token_usage: deque = deque()  # (timestamp, token_count)
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info(
            "rate_limiter_initialized",
            rpm=requests_per_minute,
            tpm=tokens_per_minute
        )
    
    async def acquire(self) -> None:
        """
        Acquire permission to make an API call.
        Blocks until rate limit allows the request.
        """
        async with self._lock:
            while True:
                now = datetime.utcnow()
                window_start = now - timedelta(minutes=1)
                
                # Clean old entries
                self._cleanup_old_entries(window_start)
                
                # Check request rate
                current_requests = len(self._request_times)
                if current_requests >= self.requests_per_minute:
                    wait_time = self._calculate_wait_time(self._request_times[0], now)
                    if wait_time > self.max_wait_seconds:
                        logger.warning("rate_limit_max_wait_exceeded", wait_time=wait_time)
                        wait_time = self.max_wait_seconds
                    
                    logger.debug("rate_limit_waiting", wait_time=wait_time, reason="rpm")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Check token rate
                current_tokens = sum(tokens for _, tokens in self._token_usage)
                if current_tokens >= self.tokens_per_minute:
                    oldest_token_time = self._token_usage[0][0] if self._token_usage else now
                    wait_time = self._calculate_wait_time(oldest_token_time, now)
                    if wait_time > self.max_wait_seconds:
                        wait_time = self.max_wait_seconds
                    
                    logger.debug("rate_limit_waiting", wait_time=wait_time, reason="tpm")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Record this request
                self._request_times.append(now)
                break
    
    def record_tokens(self, token_count: int) -> None:
        """Record token usage for a completed request."""
        now = datetime.utcnow()
        self._token_usage.append((now, token_count))
        
        logger.debug("tokens_recorded", count=token_count, total_in_window=self._get_current_token_usage())
    
    def _cleanup_old_entries(self, window_start: datetime) -> None:
        """Remove entries outside the sliding window."""
        while self._request_times and self._request_times[0] < window_start:
            self._request_times.popleft()
        
        while self._token_usage and self._token_usage[0][0] < window_start:
            self._token_usage.popleft()
    
    def _calculate_wait_time(self, oldest_time: datetime, now: datetime) -> float:
        """Calculate how long to wait until oldest entry expires."""
        window_end = oldest_time + timedelta(minutes=1)
        wait_delta = window_end - now
        return max(0.1, wait_delta.total_seconds())
    
    def _get_current_token_usage(self) -> int:
        """Get current token usage in the window."""
        return sum(tokens for _, tokens in self._token_usage)
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)
        self._cleanup_old_entries(window_start)
        
        return {
            "requests_in_window": len(self._request_times),
            "requests_limit": self.requests_per_minute,
            "tokens_in_window": self._get_current_token_usage(),
            "tokens_limit": self.tokens_per_minute,
            "requests_available": self.requests_per_minute - len(self._request_times),
            "tokens_available": self.tokens_per_minute - self._get_current_token_usage()
        }
    
    async def wait_if_needed(self, estimated_tokens: int = 0) -> None:
        """
        Proactively wait if we're close to limits.
        Useful for batching operations.
        """
        stats = self.get_stats()
        
        # If we're at 80% capacity, slow down
        if stats["requests_available"] < self.requests_per_minute * 0.2:
            await asyncio.sleep(1.0)
        
        if estimated_tokens > 0:
            if stats["tokens_available"] < estimated_tokens:
                # Wait for tokens to free up
                wait_time = min(10.0, self.max_wait_seconds)
                logger.debug("proactive_wait", estimated_tokens=estimated_tokens, wait_time=wait_time)
                await asyncio.sleep(wait_time)


class MultiTierRateLimiter:
    """
    Rate limiter that handles multiple tiers (e.g., per-user and global).
    """
    
    def __init__(
        self,
        global_rpm: int = 1000,
        global_tpm: int = 1000000,
        per_user_rpm: int = 50,
        per_user_tpm: int = 100000
    ):
        self._global_limiter = RateLimiter(
            requests_per_minute=global_rpm,
            tokens_per_minute=global_tpm
        )
        self._user_limiters: dict[str, RateLimiter] = {}
        self._per_user_rpm = per_user_rpm
        self._per_user_tpm = per_user_tpm
        self._lock = asyncio.Lock()
    
    async def acquire(self, user_id: str) -> None:
        """Acquire permission for a specific user."""
        # Get or create user limiter
        async with self._lock:
            if user_id not in self._user_limiters:
                self._user_limiters[user_id] = RateLimiter(
                    requests_per_minute=self._per_user_rpm,
                    tokens_per_minute=self._per_user_tpm
                )
        
        # Check both global and user limits
        await self._global_limiter.acquire()
        await self._user_limiters[user_id].acquire()
    
    def record_tokens(self, user_id: str, token_count: int) -> None:
        """Record token usage for both global and user limits."""
        self._global_limiter.record_tokens(token_count)
        if user_id in self._user_limiters:
            self._user_limiters[user_id].record_tokens(token_count)