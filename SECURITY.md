# Security policy

## Supported versions

Security fixes are provided for the **0.1.x** release line. Older versions are not supported. Deploy the latest compatible patch release and review the [changelog](CHANGELOG.md) for security-relevant changes.

## Report a vulnerability privately

Email **team@shannon-ai.com** with the subject `BreakFuser security report`. Do not open a public issue, post a proof of concept publicly, or send credentials. Never include private exploit artifacts or sensitive production data in public issues or pull requests.

Include:

- the affected version or commit and deployment interface;
- the impact and conditions required to trigger the issue;
- a minimal reproduction using synthetic data and a local deployment you control;
- relevant redacted logs or configuration, with credentials, private endpoints, personal data, and raw sensitive prompts removed; and
- any suggested mitigation, if available.

We will review good-faith reports, assess impact, and coordinate a fix and disclosure where appropriate. We will aim to acknowledge and update reporters as practical, but response and resolution times depend on severity, reproducibility, and maintainer capacity; no response or remediation timeline is guaranteed. Please allow a reasonable opportunity to investigate before public disclosure.

## Research scope and safe harbor

Test only software and systems you own or are explicitly authorized to assess. Avoid privacy violations, data destruction, service degradation or denial of service, social engineering, and physical intrusion. Do not access, retain, or share third-party data beyond what is strictly necessary to establish and report the issue, and stop testing if sensitive data is encountered.

We will not pursue or support legal action against good-faith security research conducted within this policy and applicable law. This safe harbor does not authorize unlawful activity, override third-party rights or policies, or create permission to test systems you do not control.

## Deployment security

BreakFuser crosses model, retrieval, browser, tool, HTTP, and MCP trust boundaries. Sanitization and verification reduce specific risks but do not replace authentication, authorization, isolation, secret management, or independent output review.

- [Security and privacy architecture](docs/security.md): trust boundaries, sanitization limits, provenance, and tenant isolation.
- [Configuration](docs/configuration.md): provider settings, budgets, privacy controls, and server authentication.
- [Deployment and integrations](docs/integrations.md): HTTP, function calling, skills, and MCP controls.
- [Troubleshooting](docs/troubleshooting.md): connectivity and operational diagnostics without sharing secrets.

For shared or non-loopback deployments, require authentication, terminate TLS at a restricted reverse proxy, isolate untrusted tenants, limit tool and network privileges, and protect provenance and browser artifacts. The local simulation browser is not a security sandbox.
