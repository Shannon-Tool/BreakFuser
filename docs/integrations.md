# Integrations

BreakFuser can run as a Python library, an OpenAI-compatible HTTP service, an ASGI application, or an MCP server. All interfaces use the same local-owned fusion pipeline and configured budgets.

## OpenAI-compatible server

After loading the real-provider environment described in [Configuration](configuration.md), start:

```bash
breakfuser serve
```

The default listener is `127.0.0.1:8000`. Override it centrally or for one command:

```bash
export BREAKFUSER_SERVER_HOST=127.0.0.1
export BREAKFUSER_SERVER_PORT=8000
breakfuser serve --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`: process/pipeline status without provider calls; remains public.
- `GET /v1/models`: the configured response-model identifier.
- `POST /v1/chat/completions`: standard JSON or server-sent event responses.

The request `model` is a compatibility alias. Provider roles and model aliases remain server configuration, not per-request routing controls.

### Standard OpenAI Python client

Install the OpenAI SDK in the application environment, then point it at BreakFuser:

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

Ordinary requests require **no custom headers and no BreakFuser-specific fields**. Standard messages, model, stream, max tokens/`max_completion_tokens`, temperature, tools, tool choice, and response format are supported.

### Plain HTTP JSON

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "breakfuser",
    "messages": [{"role": "user", "content": "Explain runtime model fusion."}]
  }'
```

The JSON response contains standard `choices` and `usage` fields plus a `breakfuser` metadata object. Optional `harvest_provenance: true` adds claim-to-source mappings; it is not required for fusion.

### Server-sent events

Use the standard `stream` field:

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "breakfuser",
    "stream": true,
    "messages": [{"role": "user", "content": "Write a concise summary."}]
  }'
```

Each event contains an OpenAI-compatible `chat.completion.chunk`, followed by `data: [DONE]`. The service completes fusion and verification before emitting chunks, so initial latency includes the entire verified response. Streaming is not upstream token passthrough.

## Authentication and TLS

Set a server Bearer key before sharing the listener:

```bash
export BREAKFUSER_SERVER_API_KEY=your-secret-from-a-secret-manager
breakfuser serve
```

Clients then send:

```http
Authorization: Bearer your-secret-from-a-secret-manager
```

The key protects `/v1/models` and `/v1/chat/completions`; `/health` remains public. Without a key, API routes are unauthenticated and should remain on trusted loopback. The built-in server does not terminate TLS. For non-loopback deployment, use an authenticated TLS reverse proxy with request-size limits, rate limits, network policy, and secret-managed credentials. The OpenAI server key does not automatically protect a separately mounted MCP HTTP transport.

A server shares one async client, session budget, and virtual-filesystem artifact store. Use separate isolated deployments for mutually untrusted tenants. See [Security and privacy](security.md).

## Function calling

Pass ordinary OpenAI function schemas:

```python
response = client.chat.completions.create(
    model="breakfuser",
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
message = response.choices[0].message
```

When the response owner proposes a call, `message.tool_calls` contains its ID, function name, and JSON-string arguments, and the finish reason is `tool_calls`. BreakFuser validates the proposal against supplied schemas but does not invoke the function.

**Tool execution remains the harness's responsibility.** The harness must authorize the operation, validate arguments for its own environment, execute the function, append the assistant message with its tool calls, and return the observation as a `tool` message with the matching `tool_call_id`. A model proposal is not an execution result. See the complete [function-call round trip](../examples/tool_call_roundtrip.py).

Tool schemas and selected skill bodies stay on the response-owner path; they are not automatically forwarded to knowledge harvesting.

## Skills

Skills use progressive disclosure: the registry exposes short descriptions, and only selected bodies are loaded into response-model context. Select registered IDs through Python or the HTTP extension field:

```json
{
  "model": "breakfuser",
  "messages": [{"role": "user", "content": "Research this topic."}],
  "skill_ids": ["research"]
}
```

Unknown skill IDs are invalid requests. This optional field is not needed for ordinary requests. MCP clients can list `breakfuser://skills` and read `breakfuser://skills/{name}` to inspect descriptions and selected bodies.

## MCP

Install the optional MCP dependencies:

```bash
python -m pip install '.[mcp]'
```

### Stdio

```bash
breakfuser mcp --transport stdio
```

Example host configuration:

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

Stdio inherits the host process's local trust boundary and environment. See the [official SDK client example](../examples/mcp_client.py).

### Streamable HTTP

```bash
breakfuser mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

The MCP endpoint is `/mcp`. Protect remote MCP HTTP separately with authenticated TLS and network controls. Do not expose it merely because the OpenAI API has a Bearer key.

Tools:

- `breakfuser_chat(message, skill_ids?, harvest_mode?, harvest_provenance?)`: structured fused completion and metadata.
- `breakfuser_harvest(question, strategy?, aggressive?)`: typed atoms, facts, turns, metrics, evidence spans, and provenance.

Resources:

- `breakfuser://skills`: skill names and descriptions.
- `breakfuser://skills/{name}`: one selected skill body.

Embed programmatically with `breakfuser.mcp_server.create_mcp_server(client=...)` or `create_mcp_server(settings=...)`. An injected async client remains caller-owned; otherwise the server creates and closes its own client.

## ASGI embedding

Create the FastAPI application directly:

```python
from breakfuser.server import create_api_app

app = create_api_app()
```

Run it with an ASGI server after loading configuration:

```bash
uvicorn your_module:app --host 127.0.0.1 --port 8000
```

To share an explicitly configured client:

```python
import os

from BreakFuser import AsyncBreakFuser
from breakfuser.server import create_api_app

engine = AsyncBreakFuser()  # Uses the already loaded environment/YAML configuration.
app = create_api_app(client=engine, api_key=os.environ["BREAKFUSER_SERVER_API_KEY"])
```

The application closes a client it creates, but an injected client remains caller-owned. The optional `api_key` argument configures the same Bearer check as `BREAKFUSER_SERVER_API_KEY`; load the actual value from a secret manager rather than source code.

## Optional per-request recovery controls

Central `HarvestPolicy` configuration is the recommended control path. Compatibility clients may also use `x-breakfuser-harvest: conservative|balanced|aggressive|off` and `x-breakfuser-harvest-provenance: true`, or the Python `headers`/`harvest_provenance` arguments. These controls are optional and never required for an ordinary request. See [Harvesting](harvesting.md) and [API reference](api.md).
