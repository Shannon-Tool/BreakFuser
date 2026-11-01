# API reference

The public package supports both `BreakFuser` and `breakfuser` imports. The capitalized package exposes the common client, settings, and harvest types:

```python
from BreakFuser import AsyncBreakFuser, BreakFuser, HarvestPolicy, Settings
```

Configure real providers as described in [Configuration](configuration.md). Model constructor arguments are aliases only; endpoints and credentials come from settings, YAML, or environment variables.

## Clients and lifecycle

```python
from BreakFuser import BreakFuser

with BreakFuser(use_decider=False) as client:
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": "Explain how a hash table works."}]
    )
    print(response.choices[0].message.content)
```

`BreakFuser` and `AsyncBreakFuser` accept `decider`, `uncensoredmodel`, and `smartmodel` aliases, plus `config_path`, `settings`, `harvest_policy`, and injectable backend, sanitizer, and browser adapters. The sync constructor also accepts `use_decider=False`; async callers can disable it in `Settings`, YAML, or the environment.

The complete fusion pipeline runs by default. Use `close()`, `await close()`, or the corresponding context manager to cancel background work and release client resources.

## Chat completions

### Synchronous

```python
response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Compare two licensing models."}],
    temperature=0,
    max_tokens=1024,
    harvest_provenance=True,
)

print(response.choices[0].message.content)
print(response.usage.total_tokens)
print(response.breakfuser.trace_id)
```

`max_tokens` applies to the response-model draft and remains capped by `BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS` or the shared output cap. `temperature` defaults to 0. `harvest_provenance=True` returns per-claim source mappings; no custom header is needed.

### Asynchronous

```python
from BreakFuser import AsyncBreakFuser

async with AsyncBreakFuser() as client:
    response = await client.chat.completions.create(
        messages=[{"role": "user", "content": "Summarize the evidence."}],
        harvest_provenance=True,
    )
    print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    messages=[{"role": "user", "content": "Write a concise summary."}],
    stream=True,
)
for chunk in stream:
    for choice in chunk.choices:
        if choice.delta.content:
            print(choice.delta.content, end="")
```

The async form awaits `create` and then uses `async for`:

```python
stream = await client.chat.completions.create(
    messages=[{"role": "user", "content": "Write a concise summary."}],
    stream=True,
)
async for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

Streaming is **buffered until fusion and verification finish**. Chunks use `object="chat.completion.chunk"`; the final chunk carries usage and the finish reason. Structured tool calls appear in delta objects. This interface does not expose upstream tokens before verification.

## Response and metadata

Responses include OpenAI-style `id`, `object`, `created`, `model`, `choices`, and `usage`, plus a `breakfuser` metadata object.

| Field | Meaning |
|---|---|
| `trace_id` | Correlation identifier for the request. |
| `pipeline_stages` | `document_retrieval`, `local_draft`, `remote_evidence`, `fusion_composition`, and `verify_after`. |
| `artifacts` | Virtual-filesystem artifact paths associated with the client. |
| `harvest` | Atomic coverage, refusal/hedge/omission, provenance, fidelity, token, latency, and turn metrics when harvesting ran. |
| `provenance` | Claims with `turn_ids`, `document_ids`, and `inferred`; returned when requested. |
| `evidence_class` | `deterministic`, `verified_remote`, `retrieved_document`, `local_inference`, or `no_verified_response`. |
| `verification_status` | `passed`, `limited`, or `not_required`. |
| `local_finish_reason` | Native response-model draft finish reason when available. |
| `missing_atoms` | Required response elements absent from the composed answer; nonempty values force limited verification. |
| `events` | Structured stage events without raw prompt/response bodies. |
| `fusion` | Detailed origin, provider, validity, attribution, corroboration, completion, composition, salvage, root-cause, and timing metadata. |

`fusion.deterministic_validity` is `passed`, `failed`, or `not_applicable`. `fusion.composition_mode` distinguishes targeted synthesis, artifact recovery, local fallback, empty output, and deterministic/compatibility passthrough. `external_corroboration` is separate from `provenance_attribution`: a source-linked remote claim is not independently confirmed merely because it has a turn ID.

## Direct harvest

Use direct harvesting when the application needs typed atoms, exact turns, facts, evidence spans, and metrics rather than only a chat response.

```python
from BreakFuser import BreakFuser, HarvestPolicy

with BreakFuser(use_decider=False) as client:
    result = client.harvest(
        "A multi-part factual question",
        policy=HarvestPolicy(
            aggressiveness="aggressive",
            max_turns=8,
            max_parallel_atoms=4,
            request_token_budget=12000,
        ),
        strategy="atomic_decomposition",  # Omit to use policy/decider selection.
    )

print(result.answer)
print(result.metrics.atomic_coverage)
for fact in result.facts:
    print(fact.text, fact.turn_id)
```

`HarvestResult` contains:

- `answer`: locally recomposed answer for direct-harvest callers.
- `facts`: complete accepted facts with atom, turn, strategy, level, prompt hash, model, endpoint, timestamp, and confidence.
- `turns`: literal sanitized prompts, remote and desanitized responses, quality, finish reason, token cost, and latency.
- `atoms`: the candidate dependency graph used for acquisition.
- `evidence_spans`: complete and explicitly partial/salvaged source text; partial spans are not promoted to facts.
- `provenance`, `metrics`, `stopped_reason`, and `metadata`.

Supply `atoms=[Atom(...)]` to provide explicit subquestions and dependencies. Omit `strategy` for policy/decider selection, or name any registered strategy to force it. Async direct harvest additionally accepts an `asyncio.Event` as `cancellation_event`. See [Harvesting](harvesting.md) for policies and recovery behavior.

## Tools, response formats, and skills

Python completions also accept:

- `tools`: OpenAI function definitions.
- `tool_choice`: provider-compatible tool selection.
- `response_format`: provider-compatible response formatting.
- `skill_ids`: selected local skill identifiers for progressive disclosure.

A successful function-call proposal appears in `choices[0].message.tool_calls`, with finish reason `tool_calls`. BreakFuser validates known names, JSON-object arguments, and required properties, but **never executes caller functions**. The harness must authorize and execute a proposal, append the assistant tool call, and return a `tool` message with the matching `tool_call_id`. See [Integrations](integrations.md) and the [round-trip example](../examples/tool_call_roundtrip.py).

## Deterministic medical calculations

```python
from breakfuser.medical import half_life, loading_dose, maintenance_dose_rate

hours = half_life(volume_of_distribution=40, clearance=4)
rate_mg_per_hour = maintenance_dose_rate(clearance=4, target_concentration=2)
loading_mg = loading_dose(volume_of_distribution=40, target_concentration=2)
```

For consistent L, L/h, and mg/L inputs, these return approximately 6.93 hours, 8 mg/h, and 80 mg. Inputs must be positive finite numbers. Loading dose is the one-compartment intravenous value before any clinically required bioavailability adjustment. These formulas are general computational utilities, not medical advice or patient-specific dosing guidance.

Fully specified supported medical questions can also use the deterministic chat fast path. Incomplete or differently formatted clinical questions are not silently treated as fully specified calculations.

## Attributed loopback pentest replay

```python
from breakfuser.pentest import PentestExecutor, PentestProposal

proposal = PentestProposal(
    method="GET",
    url="http://127.0.0.1:8080/users/1/records/2",
    expected_observation="The response owner differs from the requester.",
    remediation="Enforce object ownership on every record request.",
)
replay = await PentestExecutor().execute(proposal)
print(replay.model_proposal)
print(replay.actual_observation)
```

Run this snippet inside an async function. The executor accepts GET/POST, plain HTTP, numeric `127.0.0.1`, an explicit port, no URL credentials, and an optional JSON object body. `expected_observation` is the model proposal; `actual_observation`, status, and `sandbox_replay` come from the executor. A proposal alone is not evidence of a vulnerability. Use only against a local service you own or are explicitly authorized to test.

## Low-level access

`client.orchestrator` exposes the virtual filesystem, sanitizer, decider, browser, context compressor, DAG planner/refiner, VoI gate, skill registry, and async task manager. These interfaces share the client's configured providers and budgets.

Async task methods are `start_async_task`, `check_async_task`, `list_async_tasks`, `cancel_async_task`, and `update_async_task`. Steering uses `update_strategy="interrupt"` or `"enqueue"`; `wait_for_background(timeout=...)` supports idle wakeup. Browser methods are `browser_snapshot`, `browser_run`, `browser_screenshot`, and `browser_handoff`. `ingest_external_text` performs injection screening before storage.

Low-level DAG and adapter interfaces are intended for advanced integrations; ordinary applications should prefer chat completions, direct harvest, HTTP, or MCP.

## Errors

Python domain exceptions derive from `BreakFuserError`:

| Exception | Condition |
|---|---|
| `ConfigurationError` | Required live settings are missing or invalid. |
| `BudgetExhausted` | A request, session, token, or reported-cost ceiling is exhausted. |
| `SecurityBlocked` | A privacy, injection, or risky-tool guard blocks an operation. |
| `VerificationError` | A draft cannot be repaired to satisfy verification. |
| `AdapterError` | An upstream response or transport is invalid or unsuccessful. |
| `TaskNotFound` | An async task identifier is unknown. |
| `HarvestStopped` | Harvesting reaches a configured policy boundary. |

The HTTP server uses an OpenAI-style `error` envelope with safe messages: invalid requests return 400, authentication failures 401, security blocks 403, exhausted budgets 429, and upstream/verification failures 502. Raw prompts, credentials, and upstream response bodies are not included. See [Troubleshooting](troubleshooting.md).
