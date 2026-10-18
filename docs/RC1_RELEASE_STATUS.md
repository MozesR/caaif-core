# RC1 Release-Readiness Decision Record

**Internal candidate:** `caaif-core==0.1.0rc1`

**Decision:** Code and documentation can be reviewed locally. **Public GitHub/PyPI publication is NOT APPROVED** by this package.

#### Done in this candidate

- Consolidated importable Core SDK and opt-in guarded/distributed research profile.
- Versioned Python packaging and staged source distribution.
- Local, distributed, and optional real cross-framework demonstrations.
- Existing source/reference conformance tests and reproducible performance benchmarks.
- Draft licensing, governance, security, contribution, GitHub CI and release gates.

#### Explicit human gates

1. Establish ownership, work-for-hire permissions and third-party provenance for every source/doc/figure.
2. Have the rights holder formally adopt Apache-2.0 (or choose another appropriate license); add final LICENSE/NOTICE and project metadata.
3. Approve name/trademark, canonical repository URLs, copyright years and release maintainer.
4. Enable private vulnerability reporting and agree to security scope and response process.
5. Conduct independent code/security review appropriate for an experimental public developer preview.
6. Review release artifacts and CI workflows; record actual signoffs and tag a verified Git commit.

Security limitations such as TLS, workload identity and cross-node replay must be expressly disclosed for a developer preview; they remain hard blockers for any production security assurance.

**CI policy:** `.github/workflows/ci.yml` runs non-publishing checks only. The strict release gate must return BLOCKED until formal approvals; it is not a substitute for legal or security review.
