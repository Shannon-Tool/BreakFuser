from __future__ import annotations

import logging

import pytest

from breakfuser.budget import BudgetManager, UsageAccumulator
from breakfuser.config import BudgetSettings, HarvestPolicy, Settings, load_settings
from breakfuser.errors import BudgetExhausted, ConfigurationError
from breakfuser.models import ChatMessage
from breakfuser.orchestrator import Orchestrator
from breakfuser.telemetry import Trace, content_hash, redact


def test_yaml_environment_and_override_precedence(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "models:\n  local: yaml-local\n  smart: ${SMART_FROM_YAML}\n"
        "transport:\n  timeout_seconds: 12\n"
        "harvest:\n  aggressiveness: conservative\n"
    )
    monkeypatch.setenv("SMART_FROM_YAML", "yaml-smart")
    monkeypatch.setenv("BREAKFUSER_LOCAL_MODEL", "env-local")
    monkeypatch.setenv("BREAKFUSER_RETRIES", "4")
    settings = load_settings(str(config), models={"local": "explicit-local"})
    assert settings.models.local == "explicit-local"
    assert settings.models.smart == "yaml-smart"
    assert settings.transport.timeout_seconds == 12
    assert settings.transport.retries == 4
    assert settings.harvest.aggressiveness == "conservative"


def test_aggressive_recovery_is_the_zero_configuration_default() -> None:
    policy = HarvestPolicy()

    assert policy.aggressiveness == "aggressive"
    assert policy.allowed_levels == [0, 1, 2, 3, 4, 5]
    assert Settings().harvest.aggressiveness == "aggressive"


def test_live_validation_and_aggressive_policy() -> None:
    with pytest.raises(ConfigurationError):
        Settings(mode="live")
    policy = HarvestPolicy(aggressiveness="aggressive", enabled_strategies=["direct"])
    assert 5 in policy.allowed_levels
    assert "prefill_continuation" in policy.enabled_strategies
    assert "authority_override" in policy.enabled_strategies
    with pytest.raises(ValueError):
        HarvestPolicy(max_turns=0)


def test_request_and_session_budgets() -> None:
    root = BudgetManager(BudgetSettings(request_tokens=10, session_tokens=15, api_usd=1, gpu_usd=1))
    first = root.new_request()
    first.charge(8, api_usd=0.2, gpu_usd=0.1)
    assert first.remaining_request_tokens() == 2
    second = root.new_request()
    second.charge(6)
    with pytest.raises(BudgetExhausted):
        second.charge(2)
    third = root.new_request()
    with pytest.raises(BudgetExhausted):
        third.charge(2)
    with pytest.raises(ValueError):
        first.charge(-1)
    accumulator = UsageAccumulator(prompt_tokens=2, completion_tokens=3)
    assert accumulator.total_tokens == 5


def test_trace_redaction_and_events(caplog) -> None:
    assert "example.com" not in redact("person@example.com")
    assert "sk-value" not in redact("api_key=sk-value")
    assert len(content_hash("abc")) == 64
    trace = Trace("trace-id")
    with (
        caplog.at_level(logging.INFO, logger="breakfuser"),
        trace.span("stage", prompt="secret raw", safe="person@example.com"),
    ):
        pass
    assert trace.events[0]["trace_id"] == "trace-id"
    assert "prompt" not in trace.events[0]
    assert "person@example.com" not in caplog.text


def test_trace_normalizes_log_level_and_rejects_invalid_values() -> None:
    trace = Trace(log_level="debug")
    assert trace.log_level == "DEBUG"
    with pytest.raises(ValueError, match="Invalid trace log level"):
        Trace(log_level="verbose")


@pytest.mark.asyncio
async def test_linear_pipeline_emits_configured_debug_and_suppresses_info_at_warning(
    settings, caplog
) -> None:
    settings.trace_log_level = "DEBUG"
    orchestrator = Orchestrator(settings)
    with caplog.at_level(logging.DEBUG, logger="breakfuser"):
        response = await orchestrator.run([ChatMessage(role="user", content="Hello!")])
    debug_records = [record for record in caplog.records if record.levelno == logging.DEBUG]
    assert debug_records
    assert response.breakfuser.events
    await orchestrator.tasks.cancel_all()

    warning_settings = settings.model_copy(deep=True)
    warning_settings.trace_log_level = "WARNING"
    warning_orchestrator = Orchestrator(warning_settings)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="breakfuser"):
        warning_response = await warning_orchestrator.run(
            [ChatMessage(role="user", content="Hello!")]
        )
    assert not [record for record in caplog.records if record.levelno == logging.INFO]
    assert warning_response.breakfuser.events
    await warning_orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_legacy_pipeline_uses_configured_trace_level(settings, caplog) -> None:
    settings.trace_log_level = "DEBUG"
    orchestrator = Orchestrator(settings)
    with caplog.at_level(logging.DEBUG, logger="breakfuser"):
        await orchestrator._legacy_dag_run([ChatMessage(role="user", content="2 + 2")])
    assert [record for record in caplog.records if record.levelno == logging.DEBUG]
    await orchestrator.tasks.cancel_all()
