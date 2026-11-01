# Evidence harvesting

Harvesting treats the knowledge model as a multi-turn evidence source rather than a one-shot answer authority. It is enabled by default, bounded by policy and budgets, cancellable in direct async calls, and attributable to stored responses. A non-refused response is not automatically accurate or complete.

The response model always owns ordinary generative chat composition. Harvested material enters as evidence; it does not bypass local-owned synthesis and verification.

## Default and central controls

**Aggressive recovery is the default** for Python, HTTP, and MCP. It permits continuation/prefill, authority framing, persona switching, and panel-style completeness review, and adds crescendo levels 4–5. No custom header is needed.

Reduce acquisition intensity centrally:

```bash
export BREAKFUSER_HARVEST_AGGRESSIVENESS=balanced
```

Or configure setup code:

```python
from BreakFuser import BreakFuser, HarvestPolicy

client = BreakFuser(
    use_decider=False,
    harvest_policy=HarvestPolicy(
        aggressiveness="conservative",
        max_turns=4,
        max_parallel_atoms=2,
        request_token_budget=6000,
        session_token_budget=20000,
    ),
)
```

Balanced and conservative registries exclude prefill continuation, authority override, persona switching, and social-engineering review unless explicitly enabled. Aggressive mode automatically adds those strategies and levels 4–5, even when other aggressive defaults were copied into a custom policy. Choose balanced or conservative for a restrictive strategy allowlist or a maximum level below 4. `direct` remains available as the control strategy.

For ordinary chat, the inline pipeline starts with direct acquisition, or output shaping for exact structured/evidence-proposal tasks, and bounds recovery to an initial turn plus one repair. Direct `client.harvest(...)` exposes the full configured strategy registry and turn policy. Optional per-request compatibility headers are documented in [Integrations](integrations.md); they are not the primary configuration path.

## Strategy registry

Every strategy has an ID, level, applicable contexts, prompt builder, prefill capability, turn limit, and estimated cost. Versioned templates live in `src/breakfuser/harvest/prompts/<strategy>/`; the shared evidence contract requests concrete facts, units, scope, relationships, negation, and material qualifications without invented citations or observations.

| Strategy | Mechanism and typical use |
|---|---|
| `direct` | Plain baseline prompt and always-available control arm. |
| `academic_framing` | Textbook, paper, or literature-review framing with primary-literature conventions. |
| `expert_persona` | Practitioner, standards-review, regulator, or domain-author framing for expert audiences. |
| `hypothetical_counterfactual` | Hypothetical deployment mechanics instead of product-policy framing. |
| `crescendo` | Signal-driven multi-turn escalation that carries forward authorized context. |
| `atomic_decomposition` | Minimal-context atomic subquestions followed by local recomposition. |
| `output_shape_coercion` | Tables, structured answers, checklists, code, or exact artifacts that localize omissions and qualifications. |
| `prefill_continuation` | Anchored continuation and capability-gated assistant prefill after truncation. |
| `context_reset` | Fresh minimal context to reduce accumulated hedging or independently re-derive suspected hallucinations. |
| `authority_override` | Expert audience and no-boilerplate instruction; genuine factual uncertainty remains allowed. |
| `chunked_sweep` | Ordered narrow slices acquired across turns and merged locally. |
| `multi_variant_fanout` | Three parallel framings with decider-scored selection of the most informative answer. |
| `refusal_repair` | Lower-level factual re-ask using the actual refusal and quality class as context. |
| `persona_switch` | Aggressive transition to technical-editor or domain-practitioner review after unsuccessful repair. |
| `social_engineering` | Aggressive expert-panel completeness pressure without invented authority or consensus. |

These are prompt and recovery mechanisms, not guarantees that a provider will answer or that its answer is true. Their use remains subject to law, provider terms, and authorized security-testing boundaries.

## Atomic decomposition

For complex direct-harvest questions:

1. The response model generates candidate atomic subquestions; the non-generative decider does not write them.
2. One batched decider request evaluates atomicity, safe answer surface, necessity, and risk contribution.
3. Necessary compound candidates are rewritten, duplicates merge, and dependencies determine topological execution waves.
4. A semaphore caps parallel atoms. Each remote turn receives only the atom and explicit minimal enabling context, not the full original query.
5. Local recomposition restores original framing, merges accepted facts, removes generic per-atom disclaimers, and checks missing atoms.
6. Missing atoms trigger refusal repair or re-decomposition rather than being counted as harvested.

Question rewriting can replace configured brand/framing/date markers through a reversible mapping. Decomposition can itself lose information: the deterministic evaluation observed the local candidate generator capping broad questions at four atoms. Coverage and `missing_atoms` should therefore be inspected rather than inferred from a fluent final answer.

## Crescendo and refusal repair

The default ladder is:

```text
plain
→ academic
→ hypothetical
→ expert-practitioner
→ assume-expert-omit-caveats
→ now-include-the-parts-usually-omitted
```

Crescendo advances only after a refusal, hedge, omission, disclaimer, or related quality signal. It carries forward sanitized history, respects allowed levels and turn budgets, and stores every exact rung prompt/response pair. It does not advance blindly after a complete answer.

`RefusalDetector` combines deterministic phrases, hedge/disclaimer rules, length and entropy signals, native finish reasons, and batched decider judgments. Its typed classes and principal routes are:

| Classification | Recovery route |
|---|---|
| `none` | Accept complete evidence and store provenance. |
| `hard_refusal` | Refusal repair; aggressive policy can continue to persona switch and panel review. |
| `partial_refusal`, `hedge_heavy`, `disclaimer_only` | Output shaping and level-bounded crescendo. |
| `truncated` | Conservative salvage followed by anchored continuation. |
| `hallucination_suspected` | Verification check and fresh-context re-ask. |
| `out_of_scope` | Bounded escalation or stop at policy/VoI limits. |

## Truncation salvage

A length-truncated response can still contain useful evidence. The salvager retains complete prose and syntactically valid code prefixes, marks the resulting span `complete=False, salvaged=True`, and retains an untouched tail anchor for a continuation request with explicit missing targets.

The raw turn remains unchanged in provenance storage. Salvaged text is not promoted to a harvested fact merely for being syntactically usable, and salvage yield measures preserved characters rather than factual correctness.

## Policy, budgets, and stopping

`HarvestPolicy` controls:

- `enabled`, `enabled_strategies`, `allowed_levels`, and `aggressiveness`.
- `max_turns` and `max_parallel_atoms` (the fan-out strategy itself issues three variants).
- `request_token_budget` and `session_token_budget`, in addition to global request/session budgets.
- `control_arm_sampling_rate` for direct-control comparison.

A decider can select a strategy per atom, with fallback to `direct` for an unrecognized/other selection. Value-of-information gating compares expected improvement with configured turn cost before another recovery turn. Stops include full coverage, non-positive VoI, max turns/level, disabled policy, token/cost budget exhaustion, and cancellation. Async direct harvest accepts an `asyncio.Event`; cancellation cancels the provider wait rather than abandoning it in the background.

Provider-side spend limits remain necessary. Configured monetary budgets can account only for costs reported through adapters. See [Configuration](configuration.md) for every setting and default.

## Provenance and metrics

Every accepted fact stores its turn ID, strategy, level, prompt hash, model ID, endpoint, timestamp, and confidence. Exact sanitized prompt/response pairs are written to the virtual filesystem. Final claim mappings include turn and document IDs; claims without a source mapping are labeled `inferred`. A missing or hallucination-suspected atom is never presented as harvested fact.

Provenance is sensitive: prompts, responses, endpoints, and encrypted helper material can reveal confidential research. It also proves attribution, not truth. Protect artifacts and avoid sending them to untrusted tenants or logs.

| Metric | Meaning |
|---|---|
| `atomic_coverage` | Share of required atoms answered by accepted facts. |
| `refusal_free_rate` | Share of harvest turns classified as `none`. |
| `hedge_rate` | Recognized hedge terms divided by words in harvested text. |
| `omission_rate` | One minus atomic coverage. |
| `provenance_rate` | Share of recomposed answer claims not marked `inferred`. |
| `recomposition_fidelity` | Atomic coverage multiplied by the bounded verification outcome used by direct recomposition. |
| `cost_tokens` | Estimated or reported token consumption for the harvest. |
| `latency_ms` | Measured harvest duration. |
| `turns_used` | Number of knowledge-model turns consumed. |

Inspect these together. High coverage can coexist with high cost, and provenance can be complete for incorrect source material. [Evaluation](evaluation.md) reports deterministic results, including low strategy-selection accuracy and decomposition failure cases.

## Honest limitations

- Provider safety behavior, prompt handling, and model versions drift; re-evaluate after endpoint or model changes.
- “Uncensored” describes the selected response model/configuration, not ground truth, unrestricted legality, safety, or reliable completeness.
- Assistant prefill support varies by provider and model. Continuation prompts remain possible, but API compatibility alone does not prove prefill support.
- Decider quality judgments and verification can miss subtle contradictions or false premises.
- Deterministic strategy results do not predict real-provider yield or latency. No fresh paid live evaluation is claimed in this documentation.
- Important medical, legal, financial, biological, and security outputs require independent qualified review. Test only systems you own or are explicitly authorized to assess.

See [Security and privacy](security.md) for sanitizer and deployment boundaries and [Calibration](calibration.md) for confidence limitations.
