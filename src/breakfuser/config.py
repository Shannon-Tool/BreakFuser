"""Validated YAML/environment configuration with explicit precedence."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from breakfuser.errors import ConfigurationError


class ModelSettings(BaseModel):
    decider: str = "unspecified"
    local: str = "unspecified"
    smart: str = "unspecified"


class EndpointSettings(BaseModel):
    decider: str | None = None
    local: str | None = None
    smart: str | None = None
    browser: str | None = None


class TransportSettings(BaseModel):
    timeout_seconds: float = Field(gt=0, default=30)
    retries: int = Field(ge=0, le=10, default=2)
    max_input_tokens: int = Field(gt=100, default=32768)
    max_output_tokens: int = Field(gt=0, default=256)
    local_max_output_tokens: int | None = Field(gt=0, default=None)
    smart_max_output_tokens: int | None = Field(gt=0, default=None)

    def local_output_limit(self) -> int:
        return self.local_max_output_tokens or self.max_output_tokens

    def smart_output_limit(self) -> int:
        return self.smart_max_output_tokens or self.max_output_tokens


class BudgetSettings(BaseModel):
    request_tokens: int = Field(gt=0, default=50000)
    session_tokens: int = Field(gt=0, default=250000)
    api_usd: float = Field(gt=0, default=5)
    gpu_usd: float = Field(gt=0, default=5)


class VoISettings(BaseModel):
    turn_cost: float = Field(ge=0, default=0.05)
    commit_confidence: float = Field(ge=0, le=1, default=0.92)
    max_turns: int = Field(ge=0, default=4)


class SanitizerSettings(BaseModel):
    mode: Literal["papillon", "preempt", "pricon"] = "preempt"
    strictness: Literal["permissive", "balanced", "strict"] = "balanced"
    fallback: Literal["block", "local", "redact"] = "local"
    key: SecretStr | None = None
    routing_metadata_protection: bool = True


class BrowserSettings(BaseModel):
    provider: Literal["mock", "stagehand", "playwright"] = "mock"
    api_key: SecretStr | None = None
    model_timeout_seconds: float = Field(gt=0, default=20)


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    api_key: SecretStr | None = None


class HarvestPolicy(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = True
    enabled_strategies: list[str] = Field(default_factory=list)
    allowed_levels: list[int] = Field(default_factory=lambda: [0, 1, 2, 3])
    max_turns: int = Field(gt=0, default=8)
    max_parallel_atoms: int = Field(gt=0, default=4)
    request_token_budget: int = Field(gt=0, default=12000)
    session_token_budget: int = Field(gt=0, default=50000)
    aggressiveness: Literal["conservative", "balanced", "aggressive"] = "aggressive"
    control_arm_sampling_rate: float = Field(ge=0, le=1, default=0.1)

    @model_validator(mode="after")
    def apply_aggressive_defaults(self) -> HarvestPolicy:
        if self.aggressiveness == "aggressive":
            for strategy in (
                "prefill_continuation",
                "authority_override",
                "persona_switch",
                "social_engineering",
            ):
                if self.enabled_strategies and strategy not in self.enabled_strategies:
                    self.enabled_strategies.append(strategy)
            object.__setattr__(
                self, "allowed_levels", sorted(set(self.allowed_levels).union({4, 5}))
            )
        return self


class Settings(BaseModel):
    mode: Literal["mock", "live"] = "mock"
    models: ModelSettings = Field(default_factory=ModelSettings)
    endpoints: EndpointSettings = Field(default_factory=EndpointSettings)
    transport: TransportSettings = Field(default_factory=TransportSettings)
    budget: BudgetSettings = Field(default_factory=BudgetSettings)
    voi: VoISettings = Field(default_factory=VoISettings)
    calibration_path: str | None = None
    sanitizer: SanitizerSettings = Field(default_factory=SanitizerSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    harvest: HarvestPolicy = Field(default_factory=HarvestPolicy)
    use_decider: bool = True
    decider_api_key: SecretStr | None = None
    local_api_key: SecretStr | None = None
    smart_api_key: SecretStr | None = None
    trace_log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_live(self) -> Settings:
        if self.mode == "live":
            required = [
                ("local endpoint", self.endpoints.local),
                ("smart endpoint", self.endpoints.smart),
                ("local model", self.models.local),
                ("smart model", self.models.smart),
            ]
            if self.use_decider:
                required.extend(
                    [
                        ("decider endpoint", self.endpoints.decider),
                        ("decider model", self.models.decider),
                    ]
                )
            missing = [name for name, value in required if not value or value == "unspecified"]
            if missing:
                raise ConfigurationError(f"Live mode requires {', '.join(missing)}")
        return self


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value) or None
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _env(name: str, default: Any = None) -> Any:
    return os.getenv(f"BREAKFUSER_{name}", default)


def load_settings(config_path: str | None = None, **overrides: Any) -> Settings:
    """Load YAML, then apply environment and explicit constructor overrides."""
    data: dict[str, Any] = {}
    path = config_path or _env("CONFIG")
    if path:
        raw = yaml.safe_load(Path(path).read_text()) or {}
        if not isinstance(raw, dict):
            raise ConfigurationError("Configuration root must be a mapping")
        data = _expand_env(raw)

    env_values: dict[str, Any] = {
        "mode": _env("MODE"),
        "use_decider": _env("USE_DECIDER"),
        "calibration_path": _env("CALIBRATION_PATH"),
        "trace_log_level": _env("TRACE_LOG_LEVEL"),
        "models": {
            "decider": _env("DECIDER_MODEL"),
            "local": _env("LOCAL_MODEL"),
            "smart": _env("SMART_MODEL"),
        },
        "endpoints": {
            "decider": _env("DECIDER_ENDPOINT"),
            "local": _env("LOCAL_BASE_URL"),
            "smart": _env("SMART_BASE_URL"),
            "browser": _env("BROWSER_ENDPOINT"),
        },
        "transport": {
            "timeout_seconds": _env("TIMEOUT_SECONDS"),
            "retries": _env("RETRIES"),
            "max_input_tokens": _env("MAX_INPUT_TOKENS"),
            "max_output_tokens": _env("MAX_OUTPUT_TOKENS"),
            "local_max_output_tokens": _env("LOCAL_MAX_OUTPUT_TOKENS"),
            "smart_max_output_tokens": _env("SMART_MAX_OUTPUT_TOKENS"),
        },
        "budget": {
            "request_tokens": _env("REQUEST_TOKEN_BUDGET"),
            "session_tokens": _env("SESSION_TOKEN_BUDGET"),
            "api_usd": _env("API_BUDGET_USD"),
            "gpu_usd": _env("GPU_BUDGET_USD"),
        },
        "voi": {"turn_cost": _env("VOI_COST")},
        "sanitizer": {
            "mode": _env("SANITIZER_MODE"),
            "strictness": _env("SANITIZER_STRICTNESS"),
            "fallback": _env("SANITIZER_FALLBACK"),
            "key": _env("SANITIZER_KEY"),
        },
        "browser": {"provider": _env("BROWSER_PROVIDER"), "api_key": _env("BROWSER_API_KEY")},
        "server": {
            "host": _env("SERVER_HOST"),
            "port": _env("SERVER_PORT"),
            "api_key": _env("SERVER_API_KEY"),
        },
        "harvest": {
            "aggressiveness": _env("HARVEST_AGGRESSIVENESS"),
            "max_turns": _env("HARVEST_MAX_TURNS"),
            "max_parallel_atoms": _env("HARVEST_MAX_PARALLEL_ATOMS"),
            "request_token_budget": _env("HARVEST_REQUEST_TOKEN_BUDGET"),
            "session_token_budget": _env("HARVEST_SESSION_TOKEN_BUDGET"),
        },
        "decider_api_key": _env("DECIDER_API_KEY"),
        "local_api_key": _env("LOCAL_API_KEY"),
        "smart_api_key": _env("SMART_API_KEY"),
    }

    def merge(base: dict[str, Any], extra: dict[str, Any]) -> None:
        for key, value in extra.items():
            if value is None:
                continue
            if isinstance(value, dict):
                child = base.setdefault(key, {})
                if isinstance(child, dict):
                    merge(child, value)
            else:
                base[key] = value

    merge(data, env_values)
    merge(data, {key: value for key, value in overrides.items() if value is not None})
    return Settings.model_validate(data)
