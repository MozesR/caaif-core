# Security Policy — CAAIF Core Developer Preview

## Supported versions

No version is currently certified for production. The **experimental developer-preview release** (once publicly published) receives best-effort security fixes; older unmaintained prototypes receive no guaranteed patches. Update this table after a release is tagged.

## Report vulnerabilities privately

**Do not open a public issue containing exploit instructions, credentials or sensitive data.** Before publishing a public GitHub repo, administrators must enable **Private vulnerability reporting** (GitHub repository settings → security settings). Use GitHub's **Report a vulnerability** action under repository Security/Advisories to contact maintainers confidentially. If private reporting is unavailable, request a private contact channel without publishing sensitive details. Do not promise a contact email or SLA until a verified address and maintainers are available.

Please provide the affected version, minimal reproduction, impact, whether a fix is suggested, and safe disclosure preferences. Maintainers will acknowledge, triage, coordinate remediation, and disclose when appropriate; no fixed response timeline is promised at this stage.

## Security boundaries and limitations

- LocalController identity-binding is an in-process object-handle mechanism, **not** remote workload identity.
- The localhost HTTP examples use a research trust boundary and do not establish production TLS/mTLS, workload authentication, certificate rotation or tenant isolation.
- Context Provider policy checks in test fixtures do not prove distributed authorization enforcement under adversarial networks or concurrent revocation.
- Context references are not a substitute for access control; enforce permission at retrieval time and after policy changes.
- Never expose sample services to public networks or process real customers' regulated data without security hardening and review.
- Avoid logging tokens, sensitive prompt data, full context payloads, and provider credentials.
- Treat remote agent output as untrusted; validate requested effects and protect tools separately from CAAIF message authorization.
- Protection against replay, authorization bypass, cross-tenant leakage, and distributed race conditions remains unverified for production.

See `docs/THREAT_MODEL.md` and `RELEASE_CHECKLIST.md`.

## RC1 guarded profile

Protected actions require the guarded profile, trusted intent authority, and independent tool gateway. Static localhost bearer identities, in-memory replay tracking, incomplete four-edge distributed enforcement and bypassable network access remain open security issues. See `docs/RC1_SECURITY_ASSESSMENT.md`.
