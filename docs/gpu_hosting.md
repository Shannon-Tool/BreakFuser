# GPU hosting

BreakFuser expects an OpenAI-compatible endpoint for the response-owner role. vLLM, SGLang, Ollama, and other compatible servers can supply that role; the checkpoint, runtime, host, credentials, and GPU topology remain operator configuration.

The knowledge and optional decider roles are independent services. Hosting a response model locally does not make knowledge-provider calls local, and a hosted response endpoint does not create an on-premises trust boundary.

## Plan capacity

Record these details before choosing serving flags:

- GPU count, model, VRAM, interconnect, and available host memory/storage.
- Checkpoint path or identifier, license, quantization, and supported context length.
- Expected concurrent requests, harvest fan-out, draft/synthesis/repair calls, and output lengths.
- Target latency, uptime, network route, authentication/TLS, and hourly GPU budget.

Model weights, KV cache, activation memory, CUDA graphs, and runtime overhead all consume resources. Longer context and larger batches increase KV-cache pressure. Start with conservative context, output, and concurrency limits; raise them only after measuring memory, latency, throughput, and failure rates under representative requests.

## vLLM

Use vLLM's OpenAI-compatible server with the selected checkpoint and a stable served-model alias. A typical shape is:

```bash
vllm serve /path/to/response-model \
  --served-model-name response-model \
  --host 127.0.0.1 \
  --port 8001
```

Select tensor parallelism, maximum model length, GPU memory utilization, and concurrency for the available hardware and installed vLLM version. Then configure:

```bash
export BREAKFUSER_LOCAL_BASE_URL=http://127.0.0.1:8001/v1
export BREAKFUSER_LOCAL_MODEL=response-model
export BREAKFUSER_LOCAL_API_KEY=
```

Keep the listener private or place it behind authenticated TLS. Confirm that the selected runtime/model combination supports the message, tool, response-format, and streaming behavior your application uses.

## SGLang

Launch SGLang's OpenAI-compatible server with the checkpoint and served alias supported by the installed version, for example:

```bash
python -m sglang.launch_server \
  --model-path /path/to/response-model \
  --served-model-name response-model \
  --host 127.0.0.1 \
  --port 8001
```

Configure the same `BREAKFUSER_LOCAL_*` values shown above. Tune context, memory, scheduling, tensor parallelism, and concurrency against real workloads. Assistant prefill is provider/model dependent; OpenAI compatibility alone does not establish prefill support.

## Ollama

Expose Ollama's OpenAI-compatible endpoint and configure the exact served model identifier:

```bash
export BREAKFUSER_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export BREAKFUSER_LOCAL_MODEL=your-served-response-model
export BREAKFUSER_LOCAL_API_KEY=
```

GGUF memory requirements depend on model size, quantization, context, and offload. Use a model file and license appropriate for the deployment. Test long-context compression and parallel requests with conservative limits before increasing concurrency.

## BreakFuser resource controls

Coordinate server capacity with BreakFuser settings:

- `BREAKFUSER_MAX_INPUT_TOKENS`: compression threshold, not a substitute for the model server's actual context limit.
- `BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS`: response-role draft, decomposition, synthesis, and repair cap.
- `BREAKFUSER_SMART_MAX_OUTPUT_TOKENS`: knowledge-turn cap; independent of local GPU capacity.
- `BREAKFUSER_HARVEST_MAX_PARALLEL_ATOMS`: direct-harvest fan-out; ordinary chat uses bounded inline acquisition.
- `BREAKFUSER_REQUEST_TOKEN_BUDGET` and `BREAKFUSER_SESSION_TOKEN_BUDGET`: hard token ceilings.
- `BREAKFUSER_TIMEOUT_SECONDS` and `BREAKFUSER_RETRIES`: transport behavior under queueing and failures.

Response drafting and final synthesis are separate calls, so one user request can require multiple response-model generations. Size for the complete pipeline rather than a single completion. Monetary GPU budgets can enforce only costs reported through adapters; also configure infrastructure/provider spend controls.

## Operational validation

After loading the complete environment:

```bash
breakfuser doctor --live
```

This makes small billable calls and checks basic provider usability. Then exercise representative long context, JSON/response formats, function calling, streaming, recovery, and cancellation. Streaming remains buffered until verification, so measure time to verified response as well as upstream token latency.

Monitor GPU utilization, VRAM/KV-cache pressure, queue depth, time to first upstream token, total verified latency, output-token usage, truncation/finish reasons, retries, and errors. Increase DAG or atom fan-out only after observing stable behavior. Keep checkpoints and credentials in access-controlled storage, restrict management endpoints, and apply runtime/model updates through a repeatable rollback process.

See [Configuration](configuration.md), [Architecture](architecture.md), [Security and privacy](security.md), and [Troubleshooting](troubleshooting.md).
