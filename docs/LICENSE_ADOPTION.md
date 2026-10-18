# Apache License 2.0 — Proposal and Adoption Procedure

**Status: PROPOSAL ONLY. Not currently an authorized license grant.**

Apache-2.0 is a permissive open-source license with express patent terms and notices. The candidate full text is `LICENSE.Apache-2.0.PROPOSED`. Its inclusion is **not** a substitute for the owner(s) approving public distribution. Do not use or distribute this project as Apache-licensed until that approval is documented.

## Decisions before adoption

- Identify the correct rights holder(s), including jointly authored work and any applicable employment, client, contractor, or institutional IP terms. Do not infer ownership from who ran a developer tool.
- Verify no confidential data, employer-specific policy text, copyrighted third-party code, or secrets are included; review `docs/PROVENANCE_INVENTORY.csv` and commit history.
- Confirm external dependencies and examples are compatible; distinguish dependencies from vendored code and verify their NOTICE obligations.
- Confirm package name and repository/trademark rights separately from copyright licensing.
- Obtain permission from every necessary rights holder and keep the written sign-off outside the public repository if confidential.

## If and only if approved

1. Copy `LICENSE.Apache-2.0.PROPOSED` to a root file named `LICENSE` *without editing the license terms*.
2. Replace the proposed `NOTICE.PROPOSED.md` with an accurate `NOTICE` if legal/third-party attribution obligations apply. Do not invent a copyright holder.
3. Update `[project]` in `pyproject.toml` to add `license = "Apache-2.0"` after the owner approves that grant; set `[tool.setuptools] license-files = ["LICENSE"]` (or include `"NOTICE"` if a finalized NOTICE is present); remove the current empty list. Check packaging-backend support before building.
4. Add source SPDX headers where appropriate, after provenance review: `SPDX-License-Identifier: Apache-2.0`.
5. Verify the sdist and wheel contain the license, re-run tests, legal checks, and the release gate.
6. Record approval in the private decision log and complete `RELEASE_CHECKLIST.md`.

The Apache Software Foundation's own guidance is at https://apache.org/legal/apply-license.html and the full terms at https://www.apache.org/licenses/LICENSE-2.0 . Get qualified legal review for uncertainty about ownership or commercial use.
