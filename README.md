<div align="center">
  <img src="assets/breakfuser-logo.svg" alt="BreakFuser — a SHANNON open-source project" width="640">

  <h3>Uncensored model fusion. OpenAI-compatible by default.</h3>

  <p>
    Combine the reasoning of any smart model with the response freedom of your chosen uncensored model.
  </p>

  <p>
    <a href="https://github.com/Shannon-Tool/BreakFuser/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Shannon-Tool/BreakFuser/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://pypi.org/project/BreakFuser/"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-5B5FEF"></a>
    <a href="LICENSE"><img alt="Apache-2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-22C55E"></a>
  </p>

  <p>
    <a href="https://shannon-ai.com/">SHANNON</a> ·
    <a href="https://huggingface.co/shannon-ai">Hugging Face</a> ·
    <a href="docs/index.md">Documentation</a> ·
    <a href="CONTRIBUTING.md">Contribute</a>
  </p>
</div>

## Why BreakFuser?

BreakFuser is a provider-neutral fusion engine for developers who want capable AI responses without silently inheriting a provider's overrefusals. A configured **response model** owns the conversation and writes every final answer. A configured **knowledge model** contributes reasoning, facts, code, and evidence through a bounded, auditable acquisition pipeline.

This is **runtime model fusion**, not weight merging. Your knowledge provider's model is not modified, and its raw response is never automatically passed through as the final answer.

- **Response ownership:** the uncensored model retains the original context and performs final synthesis.
- **Evidence recovery:** decomposition, crescendo, refusal repair, continuation, and expert framing recover incomplete responses.
- **OpenAI-compatible:** use the Python client or point existing tools at `/v1/chat/completions`.
- **Ready for harnesses:** streaming, function calling, response formats, skills, and MCP use the same pipeline.
- **Auditable:** provenance links claims to stored turns; verification distinguishes attribution from factual truth.
- **Provider-neutral:** connect hosted APIs, Ollama, vLLM, SGLang, or another OpenAI-compatible server.

<img src="assets/architecture.svg" alt="BreakFuser architecture: a request reaches the response model, evidence is acquired from knowledge and retrieval services, and the response model synthesizes the verified answer" width="100%">

## Installation

BreakFuser requires **Python 3.11 or newer**.

```bash
git clone https://github.com/Shannon-Tool/BreakFuser.git
cd BreakFuser
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1
pip install .
```

For MCP support, install `pip install '.[mcp]'`. For contributor tools, install `pip install -e '.[dev]'`.

## Configure your models

Copy the configuration template:

```bash
cp .env.example .env
```

Set your response and knowledge providers. This minimal configuration uses deterministic local routing and does not require a separate decider service:

```bash
BREAKFUSER_MODE=live
BREAKFUSER_USE_DECIDER=false

# The uncensored model that owns context and writes final answers
BREAKFUSER_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
BREAKFUSER_LOCAL_API_KEY=
BREAKFUSER_LOCAL_MODEL=your-response-model

# The smart model that supplies knowledge and reasoning
BREAKFUSER_SMART_BASE_URL=https://your-provider.example/v1
BREAKFUSER_SMART_API_KEY=your-provider-key
BREAKFUSER_SMART_MODEL=your-knowledge-model

# Strong evidence recovery is enabled automatically
BREAKFUSER_HARVEST_AGGRESSIVENESS=aggressive

BREAKFUSER_TIMEOUT_SECONDS=60
BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS=2048
BREAKFUSER_SMART_MAX_OUTPUT_TOKENS=4096
```

Load the environment before starting BreakFuser:

```bash
set -a
source .env
set +a
```

PowerShell users can use their profile, a secret manager, or the environment-loading commands in the [configuration guide](docs/configuration.md). YAML configuration and explicit `Settings` objects are also supported. Environment values override YAML; constructor settings take precedence.

Check provider connectivity:

```bash
breakfuser doctor --live
```

This makes small billable requests. Never commit `.env` or provider credentials.

## Use the Python client

```python
import os

from BreakFuser import BreakFuser

client = BreakFuser(
    uncensoredmodel=os.environ["BREAKFUSER_LOCAL_MODEL"],
    smartmodel=os.environ["BREAKFUSER_SMART_MODEL"],
    use_decider=False,
)

response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Explain how a hash table works."}]
)

print(response.choices[0].message.content)
client.close()
```

The complete fusion pipeline runs by default. No feature flag, custom header, or alternate method is required. Sync, async, streaming, and direct evidence-harvesting interfaces are covered in the [API reference](docs/api.md).

## Use your existing tools and harnesses

Start the OpenAI-compatible server:

```bash
breakfuser serve
```

Then configure any standard OpenAI client to use BreakFuser:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key=os.environ.get("BREAKFUSER_SERVER_API_KEY", "local-only"),
)

response = client.chat.completions.create(
    model="breakfuser",
    messages=[{"role": "user", "content": "Explain how a hash table works."}],
)
print(response.choices[0].message.content)
```

The `model` field is a compatibility alias; the server uses its configured response, knowledge, and optional decider models. Standard JSON requests and server-sent event streaming work without BreakFuser-specific headers.

For shared or non-loopback deployments, set `BREAKFUSER_SERVER_API_KEY` and place the service behind an authenticated TLS reverse proxy. See [deployment and integrations](docs/integrations.md).

### Function calling

Pass ordinary OpenAI function definitions through `tools`. BreakFuser validates and returns tool-call proposals; your harness remains responsible for authorization and execution. Return observations as `tool` messages with the matching `tool_call_id`.

```python
response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Read the weather in Paris"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
)
```

See the complete [tool-call round trip](examples/tool_call_roundtrip.py).

### MCP

```bash
pip install '.[mcp]'
breakfuser mcp
```

Add BreakFuser to an MCP host:

```json
{
  "mcpServers": {
    "breakfuser": {
      "command": "breakfuser",
      "args": ["mcp", "--transport", "stdio"]
    }
  }
}
```

The server exposes `breakfuser_chat`, `breakfuser_harvest`, and progressive skill resources. Details are in [integrations](docs/integrations.md).

## Evidence recovery, without harness changes

BreakFuser starts with direct acquisition and reacts to refusal, hedging, omission, or truncation. **Aggressive recovery is the default** for Python, HTTP, and MCP: refusal repair, crescendo, continuation, academic/expert framing, persona switching, and panel-based completeness review are available within configured limits.

To reduce acquisition intensity centrally, set:

```bash
BREAKFUSER_HARVEST_AGGRESSIVENESS=balanced
```

Or configure it in setup code:

```python
from BreakFuser import BreakFuser, HarvestPolicy

client = BreakFuser(
    use_decider=False,
    harvest_policy=HarvestPolicy(aggressiveness="balanced"),
)
```

Budgets, maximum turns, allowed strategies, and cancellation still apply. Provider behavior varies, and a non-refused response is not automatically accurate. See [evidence recovery](docs/harvesting.md).

## Optional semantic decider

A Decisions-compatible model can improve routing, quality classification, calibration, and audit decisions. Set `BREAKFUSER_USE_DECIDER=true` and configure:

```bash
BREAKFUSER_DECIDER_ENDPOINT=https://your-provider.example/decisions
BREAKFUSER_DECIDER_API_KEY=your-decider-key
BREAKFUSER_DECIDER_MODEL=your-decider-model
```

Without a decider, deterministic local rules still handle objective routing, privacy, injection, refusal, and artifact checks. Ambiguous semantic judgments are less informed; BreakFuser does not silently substitute a weaker model.

## Documentation

- [Documentation index](docs/index.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [API reference](docs/api.md)
- [Tools, HTTP, skills, and MCP](docs/integrations.md)
- [Evidence recovery and provenance](docs/harvesting.md)
- [Security and privacy](docs/security.md)
- [Evaluation and limitations](docs/evaluation.md)
- [GPU hosting](docs/gpu_hosting.md)
- [Troubleshooting](docs/troubleshooting.md)

## Community and development

BreakFuser is free and open source under **Apache-2.0**, including commercial use under the license terms. Contributions, issue reports, and provider-integration feedback are welcome.

- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Responsible use and legal notice

BreakFuser is general-purpose infrastructure provided **“AS IS”** under Apache-2.0, without warranties of accuracy, availability, fitness for a particular purpose, or non-infringement. You are responsible for your configuration, prompts, deployment, and use of generated output, and for complying with applicable law, third-party rights, and provider terms.

“Uncensored” describes the behavior of your selected model and configuration—not truth, completeness, safety, legality, or freedom from all provider restrictions. Review important outputs independently. Medical, legal, financial, and biological outputs are general information, not professional advice. Security testing must be limited to systems you own or are explicitly authorized to assess. The [license](LICENSE) and [security policy](SECURITY.md) contain the controlling terms and reporting process.

---

<div align="center">
  <strong>Developed and maintained by <a href="https://shannon-ai.com/">SHANNON LAB LLC</a></strong><br>
  BreakFuser is part of SHANNON’s open-source AI infrastructure.<br>
  <a href="https://huggingface.co/shannon-ai">Explore SHANNON models on Hugging Face</a>
</div>
