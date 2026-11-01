# Troubleshooting

Start with the same environment used by the application, then run:

```bash
breakfuser doctor --live
```

The readiness check makes small billable response and knowledge calls, plus a decider call when enabled. It reports basic provider usability only; it does not certify answer quality, calibration, browser behavior, tool support, or prefill behavior.

Never include API keys, authorization headers, raw sensitive prompts, or unreviewed provenance in logs or issue reports. Use trace IDs, status codes, token counts, latency, finish reasons, and sanitized metadata for diagnosis.

## Configuration and connectivity

| Symptom | Checks and resolution |
|---|---|
| `ConfigurationError` in live mode | Confirm response/knowledge base URLs and model aliases. If the decider is enabled, its full endpoint and model are also required. Check `${NAME}` expansion in YAML and remember that environment values override YAML. |
| Decider should be optional | Set `BREAKFUSER_USE_DECIDER=false`, or pass `use_decider=False` to the sync constructor. For async construction, use `Settings`, YAML, or environment configuration. |
| 401/403 from an upstream provider | Verify secret injection, endpoint, model permissions, and provider account state. Do not print credentials. A model-not-granted error means the alias is unavailable to that key. |
| 404 from `/chat/completions` | Use the provider's expected OpenAI-compatible base root, normally ending in `/v1`; BreakFuser appends `/chat/completions`. |
| 404 or schema error from Decisions | Configure the full Decisions API path, not a chat-completions URL. Paths differ by provider; OpenRouter uses its documented alpha Decisions endpoint. |
| Constructor changes appear ignored | Environment values override YAML. Explicit constructor values override both. A supplied `Settings` object is already resolved and bypasses those overlays. |
| Empty response after reasoning | The output cap may be exhausted before visible content. Increase the appropriate role cap within budget and inspect native finish reasons and salvage metadata. |

Run `breakfuser serve` with the same environment that passed the readiness check. Point external harnesses to BreakFuser's `/v1` root, not directly to either upstream provider. The request `model` is a compatibility alias; it does not reroute provider roles.

## OpenAI HTTP server

- **401 from `/v1/models` or chat completions:** set the client's Bearer token to `BREAKFUSER_SERVER_API_KEY`. This server credential is separate from upstream provider keys.
- **Unauthenticated local routes:** without a configured server key, API routes do not require authentication. Keep them on trusted loopback or configure a key and authenticated TLS proxy.
- **Connection refused:** confirm host/port, process status, and that the client base URL includes `/v1`.
- **Streaming appears delayed:** expected. SSE chunks are buffered until fusion and verification complete; they are not upstream token passthrough.
- **HTTP 400:** validate messages, tools, response format, selected skill IDs, and optional recovery values.
- **HTTP 403:** a privacy or tool-security guard blocked the request; review residual sensitive entities and fallback policy rather than logging the payload.
- **HTTP 429:** inspect configured request/session budgets and parallel fan-out. Raising a ceiling increases cost exposure.
- **HTTP 502:** inspect upstream availability, timeouts, model compatibility, finish reasons, and verification metadata.

## Harvesting and verification

- **Repeated refusal or omission:** inspect `breakfuser.harvest`, `fusion.provider_outcome`, `missing_atoms`, and exact turn provenance. Aggressive recovery is enabled by default; policy levels, turns, VoI, and budgets can still stop acquisition.
- **Recovery seems less extensive in chat than direct harvest:** ordinary chat intentionally bounds inline acquisition to an initial turn plus one repair. Direct `client.harvest(...)` uses the full configured policy.
- **Aggressive strategy or level override has no effect:** aggressive mode automatically adds its advanced strategies and levels 4–5. Use balanced/conservative for a restrictive allowlist or lower level cap.
- **Repeated truncation:** inspect native `finish_reason`, `local_finish_reason`, `fusion.salvage_yield`, and output caps. Salvaged spans are explicitly partial and are not facts merely because they contain usable text.
- **Verification remains limited:** inspect `fusion.deterministic_validity`, `task_completion_status`, `root_cause_flags`, and `missing_atoms`. A source-linked claim is not independently corroborated by provenance alone.
- **Prefill has no effect:** support varies by provider and model. Continuation prompts can still operate; do not infer prefill support from OpenAI API compatibility.
- **Strategy selection is surprising:** deterministic evaluation found low oracle-selection accuracy. Force a strategy in direct harvest for controlled diagnosis, then evaluate the real provider rather than assuming selection quality.
- **Cancellation or timeout:** inspect provider latency and transport limits. Async direct harvest accepts an `asyncio.Event`; cancellation stops its provider wait.

## Budgets and cost

Token budgets cover the complete pipeline, including response drafting, harvesting, synthesis, and repair. Session budgets are shared by a client; a running HTTP server owns one shared client. Harvest policies add separate request/session ceilings.

If a budget is exhausted, reduce fan-out, turns, output caps, or request scope before raising limits. Monetary budgets account only for cost reported through adapters and do not replace provider-side spend controls or billing reconciliation.

## Function calling and skills

- **No tool call returned:** confirm that the response model supports OpenAI tools and that the request includes `tools`. Inspect finish reason and validation metadata; BreakFuser does not fabricate an execution result.
- **Invalid tool arguments:** inspect `breakfuser.fusion.root_cause_flags`. Arguments must be a JSON object with required properties. Do not execute a call marked invalid or limited.
- **No tool result in the answer:** the harness must authorize and execute the proposal, append the assistant tool call, and return a `tool` message with matching `tool_call_id`. BreakFuser never executes caller functions.
- **Unknown skill:** select only registered IDs. MCP clients can list `breakfuser://skills`; unknown IDs are invalid requests.
- **Response-format differences:** provider/model support varies. Validate the actual response owner with the required schema and inspect deterministic validity.

## Browser and MCP

- **Playwright import error:** install the browser extra and its required browser runtime using the Playwright version's documented installation process.
- **Local handoff unavailable:** local Playwright cannot issue a remote authenticated session link. Configure a Stagehand/Browserbase-compatible provider. Treat 15-minute handoff URLs as sensitive capabilities.
- **Browser timeout or navigation failure:** check network egress, page behavior, credentials, and operation timeout. Navigation uses events rather than fixed page-load sleeps.
- **MCP import error:** install `python -m pip install '.[mcp]'` and use an official SDK client compatible with the installed SDK range.
- **MCP HTTP authentication:** protect that transport separately with authenticated TLS/network controls. The OpenAI server Bearer setting is not automatically MCP middleware.
- **Cross-tenant artifacts or shared budgets:** use separate isolated processes/deployments for mutually untrusted tenants.

## Privacy and external content

If residual PII is detected after sanitization, use strict/block or local-only fallback and review recognizer coverage. Do not work around the guard by logging or forwarding the original payload. Format-preserving transformation and reversible round trips do not guarantee anonymity.

If external text is quarantined, treat it as untrusted content rather than instructions. Review source/hash metadata and retrieval policy. Browser text, tool results, and retrieved documents require the same injection boundary discipline.

For architecture and field meanings, see [Architecture](architecture.md) and [API reference](api.md). For provider setup and limits, see [Configuration](configuration.md) and [GPU hosting](gpu_hosting.md).
