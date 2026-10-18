#!/usr/bin/env python3
"""Mechanical release review only; does not independently establish legal/security facts."""
import argparse
from pathlib import Path
import json
import tomllib

ROOT=Path(__file__).resolve().parents[1]
APPROVAL_KEYS=(
    'copyright_and_provenance_cleared',
    'dependency_licenses_and_notice_reviewed',
    'security_policy_reporting_channel_configured',
    'distribution_name_and_metadata_reviewed',
    'preview_limitations_approved',
    'repository_review_and_release_signoff',
)

def inspect(root=ROOT):
    blockers=[]
    for name in ('pyproject.toml','SECURITY.md','CONTRIBUTING.md','GOVERNANCE.md',
                 'CODE_OF_CONDUCT.md','RELEASE_CHECKLIST.md','README.md',
                 '.github/workflows/ci.yml'):
        if not (root/name).is_file(): blockers.append('missing:'+name)
    p=root/'pyproject.toml'
    if p.exists():
        try:
            d=tomllib.loads(p.read_text())
            find=d.get('tool',{}).get('setuptools',{}).get('packages',{}).get('find',{})
            if 'caaif_core*' not in find.get('include',[]): blockers.append('package-discovery-not-explicit')
            if d.get('project',{}).get('version','').startswith('1.'):
                blockers.append('stable-version-not-approved-for-developer-preview')
            if (root/'LICENSE').exists() and d.get('project',{}).get('license')!='Apache-2.0':
                blockers.append('license-metadata-does-not-match-proposed-apache-adoption')
        except Exception as exc: blockers.append('invalid_pyproject:'+type(exc).__name__)
    if not (root/'LICENSE').is_file(): blockers.append('license-not-adopted: owner must approve and create LICENSE')
    approvals=root/'RELEASE_APPROVALS.json'
    if not approvals.is_file():
        blockers.append('signed-release-approvals-missing: see docs/RELEASE_APPROVALS.example.json')
    else:
        try:
            a=json.loads(approvals.read_text())
            for key in APPROVAL_KEYS:
                if a.get(key) is not True: blockers.append('approval-pending:'+key)
            if a.get('decision')!='approved_developer_preview': blockers.append('release-decision-not-approved')
            for key in ('rights_holder','maintainer','security_reviewer','release_manager','approval_date','commit'):
                if not isinstance(a.get(key),str) or not a[key].strip(): blockers.append('signoff-missing:'+key)
        except Exception as exc: blockers.append('invalid_release_approvals:'+type(exc).__name__)
    return blockers

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--strict',action='store_true',help='Exit nonzero while mechanical release blockers remain')
    args=p.parse_args()
    errors=inspect(args.root)
    print('CAAIF RELEASE REVIEW:', 'BLOCKED' if errors else 'MECHANICAL GATES SATISFIED — HUMAN REVIEW STILL REQUIRED')
    for error in errors: print(' -',error)
    print('Approvals are supplied by maintainers; this tool cannot prove ownership or security by itself.')
    return 1 if args.strict and errors else 0
if __name__=='__main__': raise SystemExit(main())
