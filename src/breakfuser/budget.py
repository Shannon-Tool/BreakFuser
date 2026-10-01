"""Thread-safe request/session token and monetary budgets."""

from __future__ import annotations

import threading

from pydantic import BaseModel, Field

from breakfuser.config import BudgetSettings
from breakfuser.errors import BudgetExhausted


class BudgetSnapshot(BaseModel):
    request_tokens: int = 0
    session_tokens: int = 0
    api_usd: float = 0
    gpu_usd: float = 0


class BudgetManager:
    def __init__(self, settings: BudgetSettings, _root: BudgetManager | None = None) -> None:
        self.settings = settings
        self.snapshot = BudgetSnapshot()
        self._session: BudgetSnapshot = _root._session if _root else BudgetSnapshot()
        self._lock: threading.Lock = _root._lock if _root else threading.Lock()

    def new_request(self) -> BudgetManager:
        return BudgetManager(self.settings, _root=self)

    def remaining_request_tokens(self) -> int:
        with self._lock:
            return self.settings.request_tokens - self.snapshot.request_tokens

    def charge(self, tokens: int = 0, api_usd: float = 0, gpu_usd: float = 0) -> None:
        if tokens < 0 or api_usd < 0 or gpu_usd < 0:
            raise ValueError("Budget charges must be non-negative")
        with self._lock:
            next_request = self.snapshot.request_tokens + tokens
            next_session = self._session.session_tokens + tokens
            if (
                next_request > self.settings.request_tokens
                or next_session > self.settings.session_tokens
            ):
                raise BudgetExhausted("Token budget exhausted")
            if self._session.api_usd + api_usd > self.settings.api_usd:
                raise BudgetExhausted("API cost budget exhausted")
            if self._session.gpu_usd + gpu_usd > self.settings.gpu_usd:
                raise BudgetExhausted("GPU cost budget exhausted")
            self.snapshot.request_tokens = next_request
            self._session.session_tokens = next_session
            self.snapshot.api_usd += api_usd
            self.snapshot.gpu_usd += gpu_usd
            self._session.api_usd += api_usd
            self._session.gpu_usd += gpu_usd

    def check(self, tokens: int = 0) -> None:
        with self._lock:
            if self.snapshot.request_tokens + tokens > self.settings.request_tokens:
                raise BudgetExhausted("Request token budget exhausted")
            if self._session.session_tokens + tokens > self.settings.session_tokens:
                raise BudgetExhausted("Session token budget exhausted")


class UsageAccumulator(BaseModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
