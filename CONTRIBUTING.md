# Contributing to CAAIF Core

We welcome contributions to the open, framework-independent protocol and SDK **after the project's license has been formally approved and published**. Before that, coordinate privately with the maintainer.

## Principles

- Keep the Core small: agent-independent interaction contracts, identity binding, least-context exchange and deny-by-default dispatch.
- The Conversational / Reasoning / Task design is an *opt-in, enforceable profile*, not a universal three-agent requirement.
- Don't introduce mandatory databases, cloud providers, LLMs, orchestrators or vendor-specific transports.
- Never weaken authorization to improve a benchmark.
- Keep real-world customer, banking or employer data out of examples and tests.

## Development

1. Fork / branch; write a focused issue describing the compatibility and risk impact.
2. Set up `python -m venv .venv` and install locally using `.venv/bin/python -m pip install -e '.[dev]'`; install `[interop]` only when testing optional frameworks.
3. Run `python -m unittest discover -s sdk_tests -v`, reference-profile tests, and release validator when available.
4. Include both positive and negative security tests, updated schemas/docs and benchmark methodology for performance claims.
5. Submit a pull request using `.github/PULL_REQUEST_TEMPLATE.md`. Maintainers review security-sensitive changes before merging.

## Authorship and provenance

Only contribute code/docs you have rights to license under the project's selected license. Document any third-party source and its license. Do not submit secrets, confidential data, or content copied from proprietary systems. Authors retain their rights under applicable law; this project does not impose an additional CLA in this initial proposal. Contribution licensing and DCO sign-off requirements must be confirmed as part of governance before public launch.

## Review and governance

Changes to the public protocol, backward compatibility, security policies, and conformance criteria require maintainer review and written rationale. Use semantic versioning with draft-stage warnings; avoid premature stable guarantees.
