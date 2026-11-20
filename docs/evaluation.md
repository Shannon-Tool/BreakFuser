# Evaluation

This page consolidates the repository's recorded deterministic experiments. They validate pipeline wiring, recovery behavior, attribution, and selected failure modes using simulated providers and synthetic fixtures. **They are not real-model quality benchmarks, production latency guarantees, or a fresh paid live-provider evaluation.**

Recorded results come from `bench/base_results.json`, `bench/modal_fusion_results.json`, and `bench/harvest/results.json`. The base and harvest results were regenerated on 2026-11-20; the modal-fusion results remain dated 2026-11-14. Timing values depend on the fixtures and host and are retained as observations, not forecasts.

## Reproduce deterministic experiments

From the repository root with Python 3.11 or newer:

```bash
python -m pip install -e '.[dev]'
python -m bench.base
python -m bench.modal_fusion_eval
python -m bench.harvest.run
```

These commands use local deterministic fixtures and require no paid provider credentials. They regenerate structured results under `bench/`. Run the project test suite separately for code-level regression coverage:

```bash
make test
```

## Local-owned fusion ablations

`bench/modal_fusion_eval.py` runs six golden cases: truncated code, truncated research prose, exact JSON, six-line poetry, a loopback pentest proposal, and empty output after reasoning-token exhaustion. Each arm receives the same fixtures.

| Arm | Cases | Substantive | Exact task checks | Verification passed | Mean salvage yield | Median latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Without salvage | 6 | 6 | 4 | 4 | 0.0000 | 69.364 |
| Remote passthrough ablation | 6 | 6 | 6 | 5 | 0.1936 | 47.051 |
| Earlier verification behavior | 6 | 6 | 6 | 5 | 0.0000 | 69.999 |
| Serial acquisition | 6 | 6 | 6 | 5 | 0.1936 | 91.380 |
| Full local-owned fusion | 6 | 6 | 6 | 5 | 0.1936 | 67.615 |

Interpretation:

- Full local-owned fusion passed 6/6 exact task checks while invoking the response model for final synthesis.
- Removing salvage reduced exact task success from 6/6 to 4/6; required implementation/context was lost in truncated cases.
- Full fusion's recorded median latency was 26.0% below serial acquisition in this run. Remote passthrough was faster, illustrating the cost of local synthesis rather than establishing a production latency ranking.
- The full pentest case passed schema/scope validation but remained `limited_missing_atoms` because its compact fixture omitted required scope/explanation atoms.
- Exact task checks are static rubric checks, not arbitrary code execution. Verification and task success are reported separately.

The remote-passthrough arm is an internal ablation, not the default product path. These results show behavioral preservation and failure handling, not superior real-model answer quality.

## Harvest strategy comparison

`bench/harvest/run.py` evaluates 70 synthetic instances across seven domains: biological/medical dosing, contested history, crypto/licensing history, legal/regulatory topics, product pricing/deprecation, security review, and usually-omitted-information queries. A rule-based simulated knowledge provider supplies labeled refusal and quality behavior.

| Arm | Coverage | Refusal-free | Hedge rate | Omission | Fidelity | Avg tokens | Avg ms | Avg turns |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Single-turn direct control | 0.500 | 0.500 | 0.0500 | 0.500 | 0.500 | 332.9 | 2.22 | 1.00 |
| `direct` | 1.000 | 0.700 | 0.0412 | 0.000 | 1.000 | 1825.3 | 6.56 | 1.90 |
| `academic_framing` | 1.000 | 0.950 | 0.0034 | 0.000 | 1.000 | 515.7 | 3.00 | 1.10 |
| `expert_persona` | 1.000 | 0.950 | 0.0034 | 0.000 | 1.000 | 438.9 | 2.62 | 1.10 |
| `hypothetical_counterfactual` | 1.000 | 0.850 | 0.0309 | 0.000 | 1.000 | 651.3 | 4.04 | 1.30 |
| `crescendo` | 1.000 | 0.700 | 0.0412 | 0.000 | 1.000 | 2423.3 | 8.46 | 1.90 |
| `atomic_decomposition` | 1.000 | 0.700 | 0.0412 | 0.000 | 1.000 | 1825.3 | 6.48 | 1.90 |
| `output_shape_coercion` | 1.000 | 0.717 | 0.0380 | 0.000 | 1.000 | 1292.7 | 5.28 | 1.70 |
| `prefill_continuation` | 1.000 | 1.000 | 0.0000 | 0.000 | 1.000 | 396.2 | 2.63 | 1.00 |
| `context_reset` | 1.000 | 0.700 | 0.0412 | 0.000 | 1.000 | 1230.3 | 5.75 | 1.90 |
| `authority_override` | 1.000 | 0.950 | 0.0034 | 0.000 | 1.000 | 438.9 | 2.80 | 1.10 |
| `chunked_sweep` | 1.000 | 0.673 | 0.0431 | 0.000 | 1.000 | 2693.4 | 8.51 | 2.20 |
| `multi_variant_fanout` | 1.000 | 0.603 | 0.0443 | 0.000 | 1.000 | 2102.4 | 9.17 | 4.00 |
| `refusal_repair` | 1.000 | 0.800 | 0.0412 | 0.000 | 1.000 | 1848.1 | 6.02 | 1.70 |
| `persona_switch` | 1.000 | 0.950 | 0.0034 | 0.000 | 1.000 | 515.7 | 3.01 | 1.10 |
| `social_engineering` | 1.000 | 0.950 | 0.0034 | 0.000 | 1.000 | 515.7 | 3.06 | 1.10 |
| Full policy | 1.000 | 0.800 | 0.0412 | 0.000 | 1.000 | 1694.5 | 5.79 | 1.70 |

The perfect coverage values are properties of the rule-based corpus and its atom fixtures. They must not be read as expected coverage on real providers. The single-turn control demonstrates why recovery logic exists in this harness; cost and refusal-free rates show that recovery is not free.

### Crescendo levels

| Maximum level | Coverage | Fidelity | Avg tokens | Avg turns |
|---:|---:|---:|---:|---:|
| 0 | 0.600 | 0.600 | 8278.5 | 2.70 |
| 1 | 0.800 | 0.800 | 4631.1 | 2.10 |
| 2 | 0.800 | 0.800 | 4639.3 | 2.10 |
| 3–5 | 1.000 | 1.000 | 2423.3 | 1.90 |

Higher caps can allow recovery without increasing turns when earlier rungs succeed. Lower caps consumed more turns in this corpus while leaving atoms uncovered. This is not a monotonic real-provider cost model.

### Decomposition limits

| Required atoms | Extracted | Coverage vs required | Fidelity | Observed failure |
|---:|---:|---:|---:|---|
| 1 | 1 | 1.000 | 1.000 | None |
| 2 | 2 | 1.000 | 1.000 | None |
| 4 | 4 | 1.000 | 1.000 | None |
| 6 | 4 | 0.667 | 1.000 | Local candidate cap loses required atoms |
| 8 | 4 | 0.500 | 1.000 | Local candidate cap loses required atoms |

This negative result is important: decomposition can lose information before any remote call. Recomposition fidelity for extracted atoms does not compensate for missing required atoms.

### Detection, selection, budgets, and provenance

- Refusal detector macro precision and recall were both 1.000 on the small labeled deterministic corpus. This does not estimate real-world detector accuracy.
- Strategy selection matched hand-labeled oracle choices only 20% of the time. The result is retained as a limitation, not tuned away.
- Conservative, balanced, and aggressive policy profiles all reached 1.000 coverage in this harness, averaging 1.70 turns. Average tokens were 1693.4, 1693.4, and 1694.5 respectively; observed latencies were 6.78, 5.98, and 5.90 ms. These tiny deterministic timings have no production latency interpretation.
- Provenance checks resolved 70 facts to exact stored turn pairs with 0 failures. This validates attribution wiring, not factual correctness.

## Base synthetic experiments

| Experiment | Recorded result | What it does and does not show |
|---|---|---|
| Batched decisions | 5.644 ms for one batch versus 27.921 ms for five sequential generative calls; 4.95× observed ratio | Demonstrates the batching harness with artificial delays, not provider latency or cost. |
| Calibration | ECE 0.1100 before and 0.1126 after isotonic fitting on the fitting set | Shows why fitting-set ECE is not validation performance; use held-out labels. |
| Sanitizer | 200/300 exact synthetic entities remained; round-trip rate 100% | Exposes recognizer leakage. Reversible transformation is not anonymity. |
| Value of information | Clarification selected in 2/4 cost conditions, saving two turns versus always-clarify | Validates cost-sensitive branching on a synthetic belief state. |
| Context recovery | Summary tier reached; exact needle and canonical transcript recovered | Validates recoverability for the fixture, not semantic summary quality. |
| Weaker-classifier cascade | Synthetic accuracy declined from 81.0% to 71.0%; production cascade disabled | Supports avoiding automatic low-confidence fallback to a weaker classifier. |

## Metric and coverage interpretation

- **Atomic coverage:** accepted facts divided by required atoms. It depends on the atom set; an incomplete decomposition understates the true omission.
- **Refusal-free rate:** share of turns classified as `none`, not a measure of truth.
- **Hedge rate:** recognized hedge terms divided by harvested words; the lexicon is incomplete.
- **Omission rate:** one minus atomic coverage in the harvest result.
- **Provenance rate:** non-inferred recomposed claims divided by extracted answer claims. It measures attribution, not independent corroboration.
- **Recomposition fidelity:** atomic coverage multiplied by the bounded verification outcome. It is not a human factuality score.
- **Salvage yield:** salvaged characters divided by all desanitized remote-response characters. It measures preservation, not validity.
- **Deterministic validity:** JSON, AST/identifier, line-count, tool-schema, or pentest checks where applicable. It is separate from semantic correctness.
- **Tokens and latency:** fixture-specific consumption and wall time. Provider pricing, network behavior, queuing, and real inference are absent from deterministic runs.

Test coverage measures executed code paths, not answer correctness. Likewise, a passing pipeline test does not establish model quality, privacy, or safety.

## Evaluating real providers

A real-provider evaluation should use authorized accounts, explicit budgets, representative labeled tasks, held-out calibration data, and stored traces. Measure coverage, omissions, contradiction rate, provenance, token/monetary cost, latency, truncation, and provider refusal behavior separately for the response and knowledge roles. Include naive single-turn controls and human review for consequential domains.

Re-run after model, endpoint, prompt-pack, or provider-policy changes. Do not compare deterministic timings above with paid-provider measurements or present provider output as ground truth. See [Calibration](calibration.md), [Harvesting](harvesting.md), and [Security and privacy](security.md).
