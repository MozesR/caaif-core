# Legal, provenance and dependency review

Release blocker until a rights holder approves code and documentation release. Inventory each important file or subtree, including generated code, snippets from documentation, model-generated examples, screenshots, and third-party modules. The owner of this repository must determine ownership and any employer/contractual restrictions; the fact that AI helped write code does not resolve those rights.

Use `docs/PROVENANCE_INVENTORY.csv` to capture origin, copyright holder, upstream license or permission evidence, modifications, and reviewer/decision. Avoid publicly embedding confidential contracts. Verify no personal data, bank/domain-specific materials, security secrets, or proprietary diagrams are copied into the generic Core.

Dependency process: generate a dependency tree/SBOM; record license identifiers and versions; review transitive runtime, optional and build dependencies; run vulnerability checking; preserve applicable notices. Do not silently vendor packages. Verify PyPI distribution name and brand/trademark conflicts. Validate export-control/sanctions obligations and privacy notices as applicable.

Suggested sign-off: rights holder, maintainer, legal reviewer if required, security reviewer, release manager. This package does not represent completed sign-off.
