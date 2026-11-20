# Security and privacy

BreakFuser coordinates models, retrieval, tools, and provenance across several trust boundaries. No single sanitizer, verifier, or browser adapter makes the overall deployment safe. Configure each boundary for the sensitivity of the data and the privileges of the calling application.

## Trust boundaries

| Boundary | Data and risk | Required operator control |
|---|---|---|
| Application ↔ orchestrator | Raw messages, tool definitions, credentials, and results enter the process. | Authenticate callers, validate request size, authorize tools, and isolate tenants. |
| Orchestrator ↔ response provider | Conversation, selected skill bodies, local drafts, and synthesis/repair context are sent to the response endpoint. | Use an approved provider and endpoint; review retention, access, and regional requirements. |
| Orchestrator ↔ knowledge provider | Minimized and sanitized harvest turns leave the local trust domain. | Apply sanitization, outbound guards, budgets, provider review, and local-only fallback where necessary. |
| Orchestrator ↔ optional decider | Reduced routing, quality, privacy, and audit state is sent for typed judgments. | Remove unnecessary context and protect decider credentials and endpoint metadata. |
| Retrieval/browser ↔ orchestrator | External text may contain prompt injection; pages and screenshots may contain secrets. | Screen external text, isolate browsing, restrict network destinations, and protect artifacts. |
| Harness ↔ tools/MCP | Model output can request actions but does not prove authorization or execution. | Enforce harness-side authorization, schema validation, sandboxing, and audit logs. |

“Local-owned” means the response role owns final synthesis. It does **not** guarantee on-premises processing: if the configured response endpoint is hosted, its prompts and context cross that provider boundary.

For a knowledge-model turn, BreakFuser constructs a minimal atom/context, sanitizes it, optionally pads routing length, runs outbound privacy/tool guards, calls the provider, desanitizes locally, classifies quality, and stores protected provenance. External HTTP documents are injection-screened before evidence storage; quarantined entries retain source/hash metadata rather than executable instructions.

## Sanitization capabilities

### Prεεmpt-style mode

The default `preempt` mode uses typed regex recognition, FF3 format-preserving encryption for longer alphanumeric groups, a reversible short-domain permutation, metric-LDP-style numeric noise, and an encoded helper containing encrypted originals. The same key supports local desanitization, while remote history retains sanitized text.

The short-domain permutation is not a standards-approved FF1 construction. Numeric noise does not create a formal end-to-end privacy guarantee. Recognition is deliberately limited and can miss names, contextual identities, free-form secrets, or semantic intent. Exact round-trip recovery does not demonstrate anonymity.

### PAPILLON-style mode

`papillon` uses the response model to create a concise remote proxy prompt after placeholder protection, then supports local aggregation of original context and remote information. It inherits both recognizer limitations and response-provider data exposure.

### PriCon-style mode

`pricon` substitutes opaque variables and reformulates the task as an abstract logical problem with an inverse mapping. It protects recognized literal entities but does not remove identifying context or guarantee semantic privacy.

### Strictness and fallback

- `strictness`: `permissive`, `balanced`, or `strict`.
- `fallback`: `local` suppresses delegated content, `redact` removes residual recognized entities, and `block` raises a security error.
- Strict mode blocks residual recognized entities. Encoded placeholders recognized by the outbound guard are excluded from residual-PII matching; direct identifiers and high-confidence decider PII detections can still block the call.

Routing-metadata protection pads text into fixed-length buckets. It cannot eliminate timing, token-count, provider, route, or behavioral side channels. Fixed local-only routing is the strongest available fallback for data that must not leave the process.

## Verification and provenance

Verification compares extracted claims with stored facts, checks omissions/contradictions, applies modality-specific deterministic validators, and performs bounded repair. It can miss subtle errors and does not convert provider output into ground truth.

Provenance establishes that text maps to stored turns or documents. Unmapped claims are marked `inferred`; hallucination-suspected responses are checked rather than promoted directly to facts. A complete provenance chain can still lead to an incorrect source statement.

Harvest artifacts contain exact sanitized prompts, remote responses, desanitized text, endpoints, model IDs, timestamps, and hashes. Sanitizer helpers and desanitized provenance are sensitive. The default virtual filesystem is process memory; any persistent implementation needs encryption, restricted filesystem permissions, retention limits, backup controls, and tenant isolation. Do not place provenance, screenshots, handoff URLs, API keys, or authorization headers in ordinary application logs.

Operational telemetry is designed to redact common secrets and exclude prompt/response bodies, but applications must review their own logs and error reporting.

## HTTP and multi-tenant deployment

`breakfuser serve` binds to loopback by default. Setting `BREAKFUSER_SERVER_API_KEY` requires Bearer authentication for `/v1/models` and `/v1/chat/completions`; `/health` remains public and exposes only process/pipeline status. Without a key, these API routes are unauthenticated.

Before exposing the service:

- Terminate TLS at an authenticated reverse proxy and restrict network access.
- Add request-size and rate limits, timeouts, secret-managed credentials, and provider-side spend limits.
- Separate mutually untrusted tenants into isolated processes/deployments. A shared server shares session budgets and virtual-filesystem artifacts.
- Keep raw credentials and unreviewed PII out of traces, support bundles, and issue reports.
- Review provider retention, training, residency, and contractual terms independently of BreakFuser settings.

The OpenAI server Bearer setting does not automatically secure MCP HTTP or browser services.

## Browser and tool isolation

The built-in development browser is not a security sandbox. Stagehand/Browserbase-compatible deployments should use the provider's remote isolation and access controls. Playwright uses navigation/event waits and timeouts, but a local browser process still needs operating-system sandboxing, filesystem restrictions, network egress policy, and credential isolation.

Remote handoff links expire after 15 minutes; treat them as bearer-like session capabilities and do not log or share them. Local Playwright cannot issue a remote authenticated handoff link. Screenshots and extracted page text can contain sensitive data and external instructions.

OpenAI function calls returned by BreakFuser are **proposals only**. BreakFuser validates known names, JSON-object arguments, and required properties but never executes caller functions or arbitrary generated code. Tool execution remains the harness's responsibility, including authorization, argument validation, sandboxing, and returning a matching `tool_call_id` observation.

The loopback pentest executor is narrowly restricted to plain HTTP, GET/POST, numeric `127.0.0.1`, an explicit port, no URL credentials, and JSON-object responses. Model predictions remain separate from actual replay observations. Use it only for services you own or are explicitly authorized to test.

## MCP isolation

MCP uses the official SDK. Stdio inherits the host process's privileges and environment, so grant only required credentials and filesystem/network access. Streamable HTTP needs its own authenticated TLS reverse proxy and network controls. MCP chat and harvest share the same client budgets and artifacts as other interfaces; isolate untrusted tenants rather than relying on tool names as a security boundary.

## Responsible and professional use

BreakFuser is provided **AS IS** under [Apache-2.0](../LICENSE), without warranties of accuracy, availability, fitness for a particular purpose, or non-infringement. Users are responsible for configuration, prompts, deployment, generated output, applicable law, third-party rights, and provider terms.

Medical, legal, financial, and biological outputs are general information, not professional advice; obtain qualified independent review for consequential decisions. Security testing must be limited to systems you own or are explicitly authorized to assess. “Uncensored” describes selected model behavior, not truth, completeness, safety, legality, or permission to perform an action.
