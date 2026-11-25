# Configuration

To make a smart model uncensored, connect it to an uncensored fusion model. BreakFuser also supports an optional decider for typed judgments. Model names are aliases passed to the configured provider; no provider, checkpoint, or credential is embedded in the package.

| Role | Setting | Responsibility |
|---|---|---|
| Uncensored model (response role) | `models.local`, `uncensoredmodel` | Owns conversation context, drafts, synthesis, repair, skills, and tool-call proposals; writes the final fused answer. |
| Smart model (knowledge role) | `models.smart`, `smartmodel` | The model being enhanced; supplies research, reasoning, code, and domain knowledge through sanitized recovery turns. |
| Optional decider | `models.decider`, `decider` | Supplies non-generative Choice, Score, and Noul judgments for routing, quality, privacy, stopping, and audits. |

“Local” identifies the uncensored response-owner role, not a requirement that the endpoint be on the same machine. Both chat roles use OpenAI-compatible endpoints.

## Real-provider setup

Set the response and knowledge providers first. This example disables the separate decider and uses deterministic local decision rules:

```bash
export BREAKFUSER_MODE=live
export BREAKFUSER_USE_DECIDER=false

export BREAKFUSER_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export BREAKFUSER_LOCAL_MODEL=your-response-model
export BREAKFUSER_LOCAL_API_KEY=

export BREAKFUSER_SMART_BASE_URL=https://knowledge-provider.example/v1
export BREAKFUSER_SMART_MODEL=your-knowledge-model
export BREAKFUSER_SMART_API_KEY=your-knowledge-provider-key

export BREAKFUSER_TIMEOUT_SECONDS=60
export BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS=2048
export BREAKFUSER_SMART_MAX_OUTPUT_TOKENS=4096
export BREAKFUSER_HARVEST_AGGRESSIVENESS=aggressive
```

Chat base URLs normally end in the provider's `/v1` root; BreakFuser appends `/chat/completions`. Consult the provider for authentication, model aliases, context limits, tool support, and retention behavior. Do not commit credentials or place them in YAML literals.

Check connectivity with:

```bash
breakfuser doctor --live
```

This makes small billable response and knowledge requests, plus a decider request when enabled. It checks basic usability, not answer quality, calibration, browser behavior, or prefill support.

If `.env` is used as a shell environment file, load it explicitly before starting the process:

```bash
set -a
source .env
set +a
```

Use a secret manager or the equivalent environment-loading mechanism for your operating system and deployment platform.

## Optional semantic decider

Set `BREAKFUSER_USE_DECIDER=true` and configure a Decisions-compatible service:

```bash
export BREAKFUSER_DECIDER_ENDPOINT=https://decider-provider.example/decisions
export BREAKFUSER_DECIDER_MODEL=your-decider-model
export BREAKFUSER_DECIDER_API_KEY=your-decider-key
```

The endpoint is the full Decisions API path, not an OpenAI chat base URL. Provider paths differ; for OpenRouter, use its documented Decisions endpoint. A decider is optional: `BREAKFUSER_USE_DECIDER=false` selects `LocalRuleDecider`, makes no backup-model calls, and leaves both chat roles active. Objective validation and privacy/injection/refusal checks still run, but ambiguous semantic judgments are less informed and are not calibrated truth.

## Precedence and loading

Configuration is applied in this order, from lowest to highest precedence:

1. Built-in defaults.
2. YAML from `config_path` or `BREAKFUSER_CONFIG`.
3. `BREAKFUSER_*` environment variables.
4. Explicit constructor overrides, including model aliases, `use_decider` on the sync client, and `harvest_policy`.

```python
from BreakFuser import BreakFuser, HarvestPolicy

client = BreakFuser(
    config_path="breakfuser.yaml",
    uncensoredmodel="response-alias",
    smartmodel="knowledge-alias",
    use_decider=False,
    harvest_policy=HarvestPolicy(aggressiveness="balanced", max_turns=6),
)
```

A supplied `Settings` object is already resolved and validated, so `BreakFuser(settings=settings)` and `AsyncBreakFuser(settings=settings)` use it directly instead of applying YAML/environment overlays. This is also how async callers provide all settings explicitly. Close clients directly or use their context managers.

## YAML

YAML supports the full settings tree. `${NAME}` references are expanded from the environment; an unset reference becomes null, which can trigger required-setting validation in live mode.

```yaml
mode: live
use_decider: false
models:
  local: ${BREAKFUSER_LOCAL_MODEL}
  smart: ${BREAKFUSER_SMART_MODEL}
endpoints:
  local: ${BREAKFUSER_LOCAL_BASE_URL}
  smart: ${BREAKFUSER_SMART_BASE_URL}
  browser: ${BREAKFUSER_BROWSER_ENDPOINT}
transport:
  timeout_seconds: 60
  retries: 2
  max_input_tokens: 32768
  max_output_tokens: 2048
  local_max_output_tokens: 2048
  smart_max_output_tokens: 4096
budget:
  request_tokens: 50000
  session_tokens: 250000
  api_usd: 5.0
  gpu_usd: 5.0
voi:
  turn_cost: 0.05
  commit_confidence: 0.92
  max_turns: 4
calibration_path: null
sanitizer:
  mode: preempt
  strictness: balanced
  fallback: local
  key: ${BREAKFUSER_SANITIZER_KEY}
  routing_metadata_protection: true
browser:
  provider: stagehand
  api_key: ${BREAKFUSER_BROWSER_API_KEY}
  model_timeout_seconds: 20
server:
  host: 127.0.0.1
  port: 8000
  api_key: ${BREAKFUSER_SERVER_API_KEY}
harvest:
  enabled: true
  aggressiveness: aggressive
  enabled_strategies: []
  allowed_levels: [0, 1, 2, 3]
  max_turns: 8
  max_parallel_atoms: 4
  request_token_budget: 12000
  session_token_budget: 50000
  control_arm_sampling_rate: 0.1
trace_log_level: INFO
```

For local browser automation, inject a configured Playwright adapter rather than assuming that an OpenAI-compatible chat setting configures a browser. Browser and MCP services have separate security boundaries; see [Security and privacy](security.md).

## Settings reference

### Models and transport

| Environment variable | YAML path | Default | Purpose |
|---|---|---|---|
| `BREAKFUSER_MODE` | `mode` | development | Set `live` for configured external providers. |
| `BREAKFUSER_USE_DECIDER` | `use_decider` | `true` | Enable the semantic decider; false selects local rules. |
| `BREAKFUSER_CONFIG` | — | unset | YAML file path. |
| `BREAKFUSER_DECIDER_MODEL` | `models.decider` | unspecified | Decider alias. |
| `BREAKFUSER_LOCAL_MODEL` | `models.local` | unspecified | Response-model alias. |
| `BREAKFUSER_SMART_MODEL` | `models.smart` | unspecified | Knowledge-model alias. |
| `BREAKFUSER_DECIDER_ENDPOINT` | `endpoints.decider` | unset | Full Decisions endpoint. |
| `BREAKFUSER_LOCAL_BASE_URL` | `endpoints.local` | unset | Response provider's OpenAI-compatible root. |
| `BREAKFUSER_SMART_BASE_URL` | `endpoints.smart` | unset | Knowledge provider's OpenAI-compatible root. |
| `BREAKFUSER_DECIDER_API_KEY` | `decider_api_key` | unset | Decider credential. |
| `BREAKFUSER_LOCAL_API_KEY` | `local_api_key` | unset | Response-provider credential. |
| `BREAKFUSER_SMART_API_KEY` | `smart_api_key` | unset | Knowledge-provider credential. |
| `BREAKFUSER_TIMEOUT_SECONDS` | `transport.timeout_seconds` | `30` | Positive provider-call timeout in seconds. |
| `BREAKFUSER_RETRIES` | `transport.retries` | `2` | Provider retries, from 0 through 10. |
| `BREAKFUSER_MAX_INPUT_TOKENS` | `transport.max_input_tokens` | `32768` | Input capacity used by context compression. |
| `BREAKFUSER_MAX_OUTPUT_TOKENS` | `transport.max_output_tokens` | `256` | Shared output cap when no role override is set. |
| `BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS` | `transport.local_max_output_tokens` | shared cap | Response-role planning, synthesis, decomposition, and repair cap. |
| `BREAKFUSER_SMART_MAX_OUTPUT_TOKENS` | `transport.smart_max_output_tokens` | shared cap | Knowledge-turn cap, including salvage continuation. |

The default shared output cap is deliberately small; raise it to fit real responses and available model context. Per-call `max_tokens` cannot exceed the response-role cap.

### Budgets and stopping

| Environment variable | YAML path | Default | Purpose |
|---|---|---|---|
| `BREAKFUSER_REQUEST_TOKEN_BUDGET` | `budget.request_tokens` | `50000` | Hard token ceiling per request. |
| `BREAKFUSER_SESSION_TOKEN_BUDGET` | `budget.session_tokens` | `250000` | Hard token ceiling shared by a client session. |
| `BREAKFUSER_API_BUDGET_USD` | `budget.api_usd` | `5.0` | Ceiling for API cost reported by providers. |
| `BREAKFUSER_GPU_BUDGET_USD` | `budget.gpu_usd` | `5.0` | Ceiling for GPU cost reported by providers. |
| `BREAKFUSER_VOI_COST` | `voi.turn_cost` | `0.05` | Cost subtracted from expected benefit before another turn. |
| — | `voi.commit_confidence` | `0.92` | Calibrated confidence threshold for committing. |
| — | `voi.max_turns` | `4` | Clarification-turn ceiling for the VoI gate. |
| `BREAKFUSER_CALIBRATION_PATH` | `calibration_path` | unset | JSON isotonic calibrator loaded for VoI confidence. |

Monetary budgets account for cost fields returned through adapters; they are not a substitute for provider-side spend limits or billing reconciliation. A server owns one async client and therefore one shared session budget.

### Privacy, browser, server, and logging

| Environment variable | YAML path | Default | Purpose |
|---|---|---|---|
| `BREAKFUSER_SANITIZER_MODE` | `sanitizer.mode` | `preempt` | `preempt`, `papillon`, or `pricon`. |
| `BREAKFUSER_SANITIZER_STRICTNESS` | `sanitizer.strictness` | `balanced` | `permissive`, `balanced`, or `strict`. |
| `BREAKFUSER_SANITIZER_FALLBACK` | `sanitizer.fallback` | `local` | Residual-entity handling: `local`, `redact`, or `block`. |
| `BREAKFUSER_SANITIZER_KEY` | `sanitizer.key` | generated | Stable key for reversible local desanitization. |
| — | `sanitizer.routing_metadata_protection` | `true` | Pad routed text into length buckets. |
| `BREAKFUSER_BROWSER_PROVIDER` | `browser.provider` | development | Select the configured browser implementation. |
| `BREAKFUSER_BROWSER_ENDPOINT` | `endpoints.browser` | unset | Stagehand/Browserbase-compatible tool service root. |
| `BREAKFUSER_BROWSER_API_KEY` | `browser.api_key` | unset | Browser-service credential. |
| — | `browser.model_timeout_seconds` | `20` | Browser operation/model timeout. |
| `BREAKFUSER_SERVER_HOST` | `server.host` | `127.0.0.1` | OpenAI HTTP and default MCP listen address. |
| `BREAKFUSER_SERVER_PORT` | `server.port` | `8000` | OpenAI HTTP and default MCP listen port. |
| `BREAKFUSER_SERVER_API_KEY` | `server.api_key` | unset | Bearer key for `/v1/models` and chat completions. |
| `BREAKFUSER_TRACE_LOG_LEVEL` | `trace_log_level` | `INFO` | Operational log level; prompt bodies are excluded. |

### Harvest policy

| Environment variable | YAML / `HarvestPolicy` field | Default | Purpose |
|---|---|---|---|
| — | `enabled` | `true` | Enable evidence harvesting. |
| `BREAKFUSER_HARVEST_AGGRESSIVENESS` | `aggressiveness` | `aggressive` | `aggressive`, `balanced`, or `conservative`. |
| — | `enabled_strategies` | all allowed by mode | Optional strategy allowlist; `direct` remains available. |
| — | `allowed_levels` | `0–3`, plus `4–5` in aggressive mode | Permitted crescendo/recovery levels. |
| `BREAKFUSER_HARVEST_MAX_TURNS` | `max_turns` | `8` | Maximum turns per direct-harvest run. |
| `BREAKFUSER_HARVEST_MAX_PARALLEL_ATOMS` | `max_parallel_atoms` | `4` | Atom concurrency cap; each multi-variant atom issues three variants. |
| `BREAKFUSER_HARVEST_REQUEST_TOKEN_BUDGET` | `request_token_budget` | `12000` | Additional harvest-run token ceiling. |
| `BREAKFUSER_HARVEST_SESSION_TOKEN_BUDGET` | `session_token_budget` | `50000` | Additional harvest-engine session ceiling. |
| — | `control_arm_sampling_rate` | `0.1` | Probability of selecting the direct control arm. |

Aggressive mode automatically enables prefill continuation, authority override, persona switching, and social-engineering completeness review, and adds levels 4–5. Use balanced or conservative mode when you need a restrictive strategy list or a level cap below 4. Ordinary chat bounds its inline acquisition to an initial turn plus one repair turn; direct `client.harvest(...)` uses the full policy. See [Harvesting](harvesting.md) for strategy behavior and [Troubleshooting](troubleshooting.md) for common configuration failures.
