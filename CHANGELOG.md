# Changelog

All notable changes to BreakFuser are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-20

### Added

- Provider-neutral runtime model fusion with response-model-owned context, synthesis, verification, and claim provenance.
- Aggressive-by-default evidence recovery with decomposition, crescendo, refusal repair, continuation, framing strategies, bounded turns, and budget controls across Python, HTTP, and MCP interfaces.
- OpenAI-compatible sync and async chat completions, streaming, response formats, function-call proposals, and an HTTP server for existing clients.
- Tool, skill, and MCP integrations, including browser adapters and asynchronous subagent workflows.
- Configurable privacy enforcement with sanitization, outbound guards, prompt-injection screening, local desanitization, and protected provenance.
- Deterministic local-simulation adapters, end-to-end tests, benchmarks, and provider-neutral examples.
- User documentation for architecture, configuration, APIs, evidence recovery, security and privacy, evaluation, GPU hosting, integrations, and troubleshooting.

### Fixed

- Recover useful evidence from truncated or empty knowledge-model responses while preserving response-model synthesis and verification.
- Preserve structured outputs and exact task constraints during evidence salvage and repair.
