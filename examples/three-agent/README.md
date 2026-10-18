# Three-Agent Reference Profile — Synthetic Example

This example models three independent **logical agent roles**, not three particular language models:

1. `demo.agent.conversational` receives an outline request and proposes an intent assessment.
2. `demo.agent.reasoning` evaluates the authorized intent and stores a trusted decision record authorizing one limited task capability.
3. `demo.agent.task` is permitted to perform the task only after the CAAIF controller verifies the trusted decision and independent execution policy.
4. Task receipt returns to Reasoning. Reasoning's response returns to Conversational for user presentation.

See `profile.json` for the four allowed role transitions, `contracts/` for the corresponding interaction contracts, and `requests/` for the expected envelopes. `trusted_decision_record.json` is an **illustrative trusted-store fixture**, not an authorization proof accepted from an untrusted agent.

**Invariant:** Conversational must never bypass Reasoning to command a protected Task operation. Task must separately pass tool authorization. The data behind each `ctx:` reference is not included in the wire envelope; version and scope are checked at retrieval time.

Validate the fixtures from repository root:

```bash
python3 tests/validate_examples.py
python3 -m unittest discover -s tests -p 'test_three_agent_profile.py' -v
```

These tests validate schemas and example decision logic, **not live cross-framework or security conformance**. A small runnable SDK, transport adapters and independent policy enforcement remain future work.
