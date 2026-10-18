# Maintainer decisions — REQUIRED before publication

Record owner, decision, date and evidence outside this repository if confidential.

| Decision | Proposed default | Status |
|---|---|---|
| Copyright owners and contributor permissions | Verify with each required rights holder | OPEN |
| Open-source license | Apache-2.0 | PROPOSED, NOT GRANTED |
| NOTICE / third-party attribution | Accurate as applicable | OPEN |
| Name and package publication | `caaif-core` candidate, verify availability | OPEN |
| Version label | `0.1.0rc1` experimental preview | PROPOSED |
| Maintainer/release manager | Owner to designate | OPEN |
| Private vulnerability channel | GitHub private vulnerability reporting | TO CONFIGURE |
| Contribution mechanism / conduct contact | Maintainer review, no CLA initially | TO CONFIRM |
| Security posture | Research/dev preview only | STATED, REVIEW PENDING |
| Repository permissions and CI secret management | Least privilege, branch protection | TO CONFIGURE |
| PyPI release | Separate approval | NOT APPROVED |
| Comparison against A2A | No superiority claim without equivalent-control benchmark | OPEN |
| WAN/TLS/real LLM evaluation | Future validation evidence | OPEN |

**Publication rule:** Do not treat a passing test or completed template as an approval to publish.

## Mechanical recording of manual approval

Copy `docs/RELEASE_APPROVALS.example.json` to `RELEASE_APPROVALS.json` only after actual signed decisions, and fill each confirmation accurately. The gate can check completeness but **cannot verify the truth** of signoffs. CI cannot replace human/legal/security review.
