# BreakFuser documentation

BreakFuser is SHANNON LAB LLC's Apache-2.0 runtime model-fusion engine. A configured **response model** owns the conversation and writes the final answer; a configured **knowledge model** contributes evidence through bounded, attributable acquisition. The service is provider-neutral and exposes Python, OpenAI-compatible HTTP, and MCP interfaces.

BreakFuser fuses model outputs at runtime. It does not merge model weights, and a complete knowledge-provider response does not bypass local-owned synthesis and verification.

## Choose a journey

| I want to… | Start here |
|---|---|
| Connect response and knowledge providers | [Configuration](configuration.md) |
| Call the sync or async Python API | [API reference](api.md) |
| Use an existing OpenAI-compatible application | [Integrations](integrations.md) |
| Understand response ownership and evidence flow | [Architecture](architecture.md) |
| Control evidence recovery, turns, and cost | [Harvesting](harvesting.md) |
| Deploy with privacy and isolation controls | [Security and privacy](security.md) |
| Interpret deterministic evaluation results | [Evaluation](evaluation.md) |
| Host the response model on GPUs | [GPU hosting](gpu_hosting.md) |
| Resolve connectivity, budget, or provider errors | [Troubleshooting](troubleshooting.md) |

## Quick start

Install Python 3.11 or newer, configure real providers, and check connectivity:

```bash
python -m pip install .
breakfuser doctor --live
```

Then use the ordinary chat-completions interface. The full fusion pipeline runs by default; no custom header or feature flag is required.

```python
from BreakFuser import BreakFuser

with BreakFuser(use_decider=False) as client:
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": "Explain how a hash table works."}]
    )
    print(response.choices[0].message.content)
```

For an existing harness, run `breakfuser serve` and use `http://127.0.0.1:8000/v1` as its OpenAI-compatible base URL. Streaming is buffered until fusion and verification finish. Returned function calls are proposals; the calling harness must authorize and execute them.

## Documentation map

- [Architecture](architecture.md): fusion stages, evidence model, context management, and trust boundaries.
- [Configuration](configuration.md): environment, YAML, constructor precedence, provider roles, policies, and budgets.
- [API reference](api.md): sync, async, streaming, direct harvesting, metadata, deterministic utilities, and errors.
- [Integrations](integrations.md): OpenAI clients, plain HTTP, JSON/SSE, function calling, skills, MCP, and ASGI.
- [Harvesting](harvesting.md): all 15 strategies, recovery behavior, provenance, limits, and metrics.
- [Security and privacy](security.md): sanitization, deployment controls, tool isolation, and responsible use.
- [Evaluation](evaluation.md): reproducible deterministic results and their limits.
- [Calibration](calibration.md): confidence recalibration, low-confidence behavior, and provider drift.
- [GPU hosting](gpu_hosting.md): vLLM, SGLang, Ollama, capacity, and operational checks.
- [Troubleshooting](troubleshooting.md): configuration, connectivity, verification, budgets, and integrations.

## Runnable examples

- [Simple chat](../examples/simple_chat.py)
- [Multi-turn research](../examples/deep_research.py)
- [Direct harvest](../examples/direct_harvest.py)
- [Sanitized delegation](../examples/sanitized_delegation.py)
- [Async subagent steering](../examples/async_subagent.py)
- [Browser handoff](../examples/browser_handoff.py)
- [Plain HTTP client](../examples/api_client.py)
- [Function-call round trip](../examples/tool_call_roundtrip.py)
- [MCP stdio client](../examples/mcp_client.py)

## Project and legal

BreakFuser is developed by [SHANNON LAB LLC](https://shannon-ai.com/). Explore [SHANNON models on Hugging Face](https://huggingface.co/shannon-ai). The software is provided **AS IS** under [Apache-2.0](../LICENSE). You are responsible for deployment, provider terms, applicable law, and review of generated output. It does not provide professional advice; security testing is limited to systems you own or are explicitly authorized to assess.
