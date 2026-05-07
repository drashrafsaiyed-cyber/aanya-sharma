"""
Rate Limiter — manages all free-tier API quotas
Token bucket algorithm per service
"""
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict
from utils.logger import get_logger

log = get_logger("rate_limiter")


@dataclass
class ServiceLimits:
    rpm: int        # requests per minute
    rpd: int        # requests per day
    name: str


# Free tier limits — DO NOT EXCEED
SERVICE_LIMITS: Dict[str, ServiceLimits] = {
    "groq":      ServiceLimits(rpm=30,  rpd=14400, name="Groq"),
    "gemini":    ServiceLimits(rpm=15,  rpd=1500,  name="Gemini"),
    "hf":        ServiceLimits(rpm=10,  rpd=500,   name="HuggingFace"),
    "youtube":   ServiceLimits(rpm=100, rpd=300,   name="YouTube API"),  # unit-based
    "instagram": ServiceLimits(rpm=60,  rpd=500,   name="Instagram API"),
    "reddit":    ServiceLimits(rpm=60,  rpd=1000,  name="Reddit API"),
    "gdrive":    ServiceLimits(rpm=100, rpd=5000,  name="Google Drive"),
    "pollinations": ServiceLimits(rpm=20, rpd=2000, name="Pollinations"),
}


class TokenBucket:
    """Thread-safe token bucket rate limiter"""
    def __init__(self, rpm: int):
        self.capacity = rpm
        self.tokens = rpm
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            refill = elapsed * (self.capacity / 60.0)
            self.tokens = min(self.capacity, self.tokens + refill)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: int = 1):
        while not self.consume(tokens):
            time.sleep(0.5)


class DailyCounter:
    """Tracks daily request counts"""
    def __init__(self, limit: int):
        self.limit = limit
        self.count = 0
        self.reset_time = time.time() + 86400  # 24h
        self.lock = threading.Lock()

    def check_and_increment(self) -> bool:
        with self.lock:
            if time.time() > self.reset_time:
                self.count = 0
                self.reset_time = time.time() + 86400
                log.info("Daily counter reset")

            if self.count < self.limit:
                self.count += 1
                return True
            return False

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)


class RateLimiter:
    """Central rate limiter for all services"""

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._daily: Dict[str, DailyCounter] = {}

        for service, limits in SERVICE_LIMITS.items():
            self._buckets[service] = TokenBucket(limits.rpm)
            self._daily[service] = DailyCounter(limits.rpd)

    def acquire(self, service: str, units: int = 1) -> bool:
        """
        Acquire permission to make a request.
        Returns True if allowed, False if daily limit hit.
        Blocks until rate (per-minute) limit clears.
        """
        if service not in self._buckets:
            log.warning(f"Unknown service '{service}', allowing by default")
            return True

        if not self._daily[service].check_and_increment():
            log.error(f"[{service}] DAILY LIMIT REACHED ({SERVICE_LIMITS[service].rpd} req/day)")
            return False

        self._buckets[service].wait_and_consume(units)
        remaining = self._daily[service].remaining
        log.debug(f"[{service}] Request granted | {remaining} daily remaining")
        return True

    def remaining(self, service: str) -> int:
        if service not in self._daily:
            return 0
        return self._daily[service].remaining

    def status(self) -> Dict[str, int]:
        return {s: self._daily[s].remaining for s in self._daily}


# Singleton
_limiter = None

def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
