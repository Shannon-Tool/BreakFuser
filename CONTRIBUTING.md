# Contributing to BreakFuser

Thank you for helping improve BreakFuser. Bug reports, focused fixes, documentation, tests, and provider-neutral integrations are welcome. By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up a development environment

BreakFuser requires Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make install
```

The test suite, end-to-end tests, and deterministic benchmarks use local simulation and need no paid provider credentials. Keep real credentials in your local environment or a secret manager; never commit them or place them in tests, fixtures, issues, or pull requests.

## Make a focused change

1. Create a topic branch from `main`, such as `fix/context-recovery` or `docs/provider-setup`.
2. Discuss substantial interface or architecture changes in an issue before investing in a large patch.
3. Write a failing regression test first, then implement the smallest change that makes it pass, and refactor with the test still green.
4. Match existing APIs, typing, formatting, and error-handling conventions. Keep unrelated cleanup out of the change.
5. Make small, reviewable commits with clear imperative messages. Do not commit generated caches, credentials, local traces, or sensitive artifacts.
6. Run the relevant checks, update documentation, and open a pull request using the provided template.

## Quality commands

Run individual checks while iterating:

```bash
make lint        # Ruff lint and formatting checks
make typecheck   # Strict mypy checks
make test        # Standard tests and both coverage gates
make e2e         # End-to-end public API tests
make bench       # Deterministic benchmarks
make package     # Build the wheel and source distribution
```

Before submitting a complete change, run:

```bash
make acceptance
```

Use `make clean` to remove generated build, coverage, and cache outputs. If a check fails, reproduce it locally and report the exact command and relevant redacted output rather than suppressing the check.

## Documentation and prompt packs

Update user-facing documentation when behavior, configuration, interfaces, limitations, or security guidance changes. Keep links valid and examples runnable with the supported Python versions. Use precise provider-neutral terminology and distinguish response ownership, evidence recovery, attribution, and factual verification.

Evidence-recovery prompt templates live under `src/breakfuser/harvest/prompts/`. Keep template edits versioned and reviewable, preserve required placeholders and output contracts, and add focused coverage for changed behavior. Record the exact prompt/response pair used by an experiment; do not claim a technique succeeded without stored evidence. Evaluate semantic preservation and unintended changes in recovery behavior rather than judging wording alone.

## Benchmark honesty

Use deterministic fixtures for regression comparisons and identify the host, configuration, dataset, and command when reporting measurements. Separate local-simulation results from paid-provider evaluations. Never present synthetic coverage, latency, refusal, or privacy metrics as real-model guarantees. Include failed and negative results, retain single-turn controls where relevant, and disclose changes to datasets or scoring. Provenance demonstrates attribution to a stored response, not factual truth.

## Legal, security, and privacy

Contributions are licensed under [Apache-2.0](LICENSE). Submit only work you have the right to contribute and preserve applicable copyright and license notices. Review third-party dependencies and provider terms before adding integrations.

Follow the [security and privacy guidance](docs/security.md) for sanitization, tool authorization, browser isolation, HTTP, and MCP changes. Security testing must be limited to systems you own or are explicitly authorized to assess. Do not include exploit artifacts against third-party systems, private data, or credentials in public discussion.

Report suspected vulnerabilities privately to **team@shannon-ai.com** as described in [SECURITY.md](SECURITY.md); do not open a public issue. For deployment configuration help, use the [configuration guide](docs/configuration.md) and [troubleshooting guide](docs/troubleshooting.md).
