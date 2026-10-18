#!/usr/bin/env python3
"""CAAIF Core consolidated validation and honest release-readiness report.

Uses standard library only. Runs subprocesses from the project directory; does
not modify caaif_core or read/print credentials. Exit 0 means executable gates
passed, NOT that the project is publicly releasable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import signal
import platform
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CORE = [
    'caaif_core/local.py',
    'caaif_core/provider_dispatch_v010.py',
    'caaif_core/remote_provider_v09.py',
    'caaif_core/http_transport.py',
    'examples/sdk_integrated_remote_v010_demo.py',
    'examples/three-agent/profile.json',
    'benchmarks/integrated_v0111/compare.py',
]


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def find_python() -> str:
    return str(Path(sys.executable).resolve())


def check_sources(root: Path) -> list[str]:
    return [rel for rel in REQUIRED_CORE if not (root / rel).is_file()]


def check_releasability(root: Path) -> list[dict[str, str]]:
    """Review gaps are distinct from executable test failures."""
    issues = []
    def issue(code, message, category='release'):
        issues.append({'code': code, 'message': message, 'category': category})
    if not any((root / x).exists() for x in ('LICENSE', 'LICENSE.md', 'LICENSE.txt')):
        issue('LICENSE_NOT_SELECTED', 'An explicit open-source license and copyright/provenance review are required.')
    if not any((root / x).exists() for x in ('pyproject.toml', 'setup.py', 'setup.cfg')):
        issue('DISTRIBUTION_NOT_PACKAGED', 'No installable package manifest was found.')
    if not any((root / x).exists() for x in ('SECURITY.md', '.github/SECURITY.md')):
        issue('NO_SECURITY_POLICY', 'Publish supported versions, vulnerability reporting and security limitations.')
    if not any((root / x).exists() for x in ('CONTRIBUTING.md', '.github/CONTRIBUTING.md')):
        issue('NO_CONTRIBUTING_GUIDE', 'Add a contributor guide and governance process.')
    if not (root / '.github/workflows').is_dir():
        issue('NO_PUBLIC_CI', 'Configure CI for supported Python versions.')
    if not (root / 'README.md').exists():
        issue('NO_PROJECT_README', 'Add an SDK-first README with five-minute quickstart.')
    # Explicit evidence gaps: cannot be automatically inferred from local test success.
    issue('NO_A2A_COMPARATOR', 'No independently tested equivalent-control A2A baseline; do not claim A2A superiority.', 'evidence')
    issue('NO_EXTERNAL_SECURITY_REVIEW', 'Local tests do not establish production security, TLS/network identity or third-party audit.', 'evidence')
    issue('NO_REAL_LLM_TOKEN_BENCHMARK', 'No real-model token/cost or representative workload results have been provided.', 'evidence')
    issue('NO_WAN_LOAD_TEST', 'Loopback-only benchmark; WAN/TLS/concurrency and hostile network conditions remain untested.', 'evidence')
    return issues


def safe_log(text: str) -> str:
    # Defensive redaction for subprocess output, not a full DLP engine.
    text = re.sub(r'(?i)(Bearer\s+)[^\s\"\']+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|secret|token|password)\s*[=:]\s*)[^\s,]+', r'\1[REDACTED]', text)
    return text


def run_step(root: Path, report_dir: Path, name: str, argv: list[str], timeout: int,
             required: bool=True) -> dict[str, Any]:
    print(f'[{name}] starting', flush=True)
    start=time.monotonic()
    status='FAIL'; returncode=None; output=''; reason=''
    try:
        # New process group: a timed-out multi-process benchmark must not
        # strand the Context Provider or agent workers in the background.
        with subprocess.Popen(argv, cwd=root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              start_new_session=(os.name=='posix'),
                              env={**os.environ, 'PYTHONUNBUFFERED':'1'}) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name=='posix':
                    os.killpg(proc.pid,signal.SIGKILL)
                else:
                    proc.kill()
                stdout,stderr=proc.communicate()
                status='FAIL'; reason=f'timeout_{timeout}s'
            output=stdout+'\n'+stderr
            returncode=proc.returncode
            if not reason:
                status='PASS' if returncode==0 else 'FAIL'
                if status=='FAIL': reason=f'exit_code={returncode}'
    except OSError as exc:
        output=str(exc); status='FAIL'; reason='command_unavailable'
    elapsed=round(time.monotonic()-start,2)
    outname=re.sub('[^a-zA-Z0-9_-]', '_',name)+'.log'
    (report_dir/'logs'/outname).write_text(safe_log(output),encoding='utf-8')
    tests_match=re.findall(r'Ran (\d+) tests?',output)
    tests=int(tests_match[-1]) if tests_match else None
    if status=='PASS' and tests==0:
        status='FAIL'; reason='zero_tests_executed'
    print(f'[{name}] {status} ({elapsed:.2f}s)'+(f'; tests={tests}' if tests is not None else ''), flush=True)
    return {'name':name,'status':status,'required':required,'duration_s':elapsed,
            'command': ' '.join(shlex.quote(x) for x in argv),
            'returncode':returncode,'test_count':tests,'reason':reason,
            'log':f'logs/{outname}'}


def skipped(name: str, reason: str, required: bool=False):
    print(f'[{name}] SKIP: {reason}',flush=True)
    return {'name':name, 'status':'SKIP', 'required':required, 'reason':reason}


def check_benchmark(data: dict[str, Any]) -> list[str]:
    failures=[]
    results=data.get('results',[])
    if len(results)!=2 or {r.get('case') for r in results}!={'small','large'}:
        return ['benchmark_results_missing_small_or_large']
    for r in results:
        if not r.get('revocation_tested'):
            failures.append(r.get('case','?')+'_revocation_missing')
        if r.get('http_requests') != 20:
            failures.append(r.get('case','?')+'_request_count_mismatch')
        for key in ('p50_ms','p95_ms','measured_combined_bytes'):
            if not isinstance(r.get(key),(float,int)) or r[key]<=0:
                failures.append(r.get('case','?')+'_invalid_'+key)
        stages=r.get('operation_profile',{})
        wanted={'publication':4,'provider_read_and_auth':8,'worker_dispatch':4,'callback_retrieval':4}
        for label,n in wanted.items():
            if stages.get(label,{}).get('calls')!=n:
                failures.append(r.get('case','?')+'_stage_'+label)
    return failures


def write_markdown(report: dict[str, Any]) -> str:
    checks=report['checks']; failures=[c for c in checks if c['required'] and c['status']!='PASS']
    badge='PASS — release review open' if not failures else 'FAIL — validation incomplete'
    lines=[f'# CAAIF Core release-validation report', '', f'**Validation:** {badge}',
           f'**Timestamp (UTC):** {report["timestamp_utc"]}',
           f'**Interpreter:** {report["environment"]["python"]}',
           f'**Platform:** {report["environment"]["platform"]}',
           '**Meaning:** A test pass does NOT imply production security or open-source release approval.',
           '', '## Executable validation', '', '| Check | Status | Tests | Duration |',
           '|---|---|---:|---:|']
    for c in checks:
        lines.append(f'| {c["name"]} | {c["status"]} | {c.get("test_count") or "—"} | {str(c.get("duration_s", "—"))} |')
    bench=report.get('benchmark')
    if bench:
        lines+=['','## Integrated profiler (localhost synthetic workload)','',
                '| Case | HTTP calls | Measured bytes* | P50 ms | P95 ms | Publication bytes |',
                '|---|---:|---:|---:|---:|---:|']
        for r in bench.get('results',[]):
            lines.append(f'| {r["case"]} | {r["http_requests"]} | {r["measured_combined_bytes"]} | {r["p50_ms"]} | {r["p95_ms"]} | {r["operation_profile"].get("publication",{}).get("combined_bytes","—")} |')
        lines+=['','*Client HTTP request bytes including request headers + response body bytes; excludes response headers, TLS, TCP and WAN.','The provider authorizes each read, but this benchmark does not time policy computation separately.','No fair A2A comparison or LLM token benchmark was performed.']
    lines+=['', '## Open release-review items (not automatically passed)', '']
    for item in report['release_review']:
        lines.append(f'- **{item["code"]}:** {item["message"]}')
    lines+=['','## Decision', '',
            ('All required automated checks passed; **NOT APPROVED for public v1.0 release** until release-review items are addressed.' if not failures else 'Automated validation failed. Correct failing gates before any release decision.'),
            '', 'Logs and structured results are stored next to this report. Test data is synthetic.']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['full','quick'],default='full',help='full includes integrated benchmark')
    parser.add_argument('--out',type=Path,default=Path('validation_reports/latest'))
    parser.add_argument('--runs',type=int,default=20,help='benchmark requests per small/large case')
    parser.add_argument('--warmup',type=int,default=5)
    parser.add_argument('--large-bytes',type=int,default=18000)
    parser.add_argument('--timeout',type=int,default=90,help='timeout per check in seconds; timed-out child services are stopped')
    args=parser.parse_args(argv)
    if args.runs<1 or args.warmup<0 or args.timeout<10:
        parser.error('invalid benchmark arguments')
    out=(ROOT/args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    if out==ROOT or ROOT not in out.parents:
        parser.error('--out must be a child directory of the project; do not overwrite project files')
    (out/'logs').mkdir(parents=True,exist_ok=True)
    py=find_python(); checks=[]
    missing=check_sources(ROOT)
    if missing:
        checks.append({'name':'Project source inventory','status':'FAIL','required':True,'reason':', '.join(missing)})
    else:
        checks.append({'name':'Project source inventory','status':'PASS','required':True})
    checks.append(run_step(ROOT,out,'Validator self tests',[py,'-m','unittest','discover','-s','tools/tests','-p','test_*.py','-v'],args.timeout))
    if (ROOT/'sdk_tests').is_dir():
        checks.append(run_step(ROOT,out,'SDK regressions',[py,'-m','unittest','discover','-s','sdk_tests','-v'],args.timeout))
    else:
        checks.append({'name':'SDK regressions','status':'FAIL','required':True,'reason':'sdk_tests_missing'})
    if (ROOT/'tests/test_three_agent_profile.py').is_file():
        checks.append(run_step(ROOT,out,'Three-agent profile fixtures',[py,'-m','unittest','discover','-s','tests','-p','test_three_agent_profile.py','-v'],args.timeout))
    else:
        checks.append({'name':'Three-agent profile fixtures','status':'FAIL','required':True,'reason':'tests/test_three_agent_profile.py_missing'})
    if (ROOT/'tests/validate_examples.py').is_file():
        if importlib.util.find_spec('jsonschema'):
            checks.append(run_step(ROOT,out,'Schema example validation',[py,'tests/validate_examples.py'],args.timeout))
        else:
            checks.append(skipped('Schema example validation','jsonschema not installed',required=True))
    else:
        checks.append(skipped('Schema example validation','draft example schema validator missing',required=True))
    checks.append(run_step(ROOT,out,'Integrated Controller Provider smoke',[py,'examples/sdk_integrated_remote_v010_demo.py'],args.timeout))
    for dirpart,pattern,label in [
        ('benchmarks/integrated_v011','test_integrated_wire_v011.py','Integrated wire tests'),
        ('benchmarks/integrated_v0111','test_operation_profile_v0111.py','Operation profiler tests')]:
        if (ROOT/dirpart/pattern).is_file():
            checks.append(run_step(ROOT,out,label,[py,'-m','unittest','discover','-s',dirpart,'-p',pattern,'-v'],args.timeout))
        else:
            checks.append({'name':label,'status':'FAIL','required':True,'reason':'benchmark_tests_missing'})
    if importlib.util.find_spec('langgraph') and importlib.util.find_spec('agent_framework'):
        checks.append(run_step(ROOT,out,'Real cross-framework smoke',[py,'examples/sdk_cross_framework_v04_demo.py'],args.timeout))
    else:
        checks.append(skipped('Real cross-framework smoke','optional langgraph and/or agent_framework dependency not installed',required=True))
    benchmark=None
    if args.mode=='full':
        raw=out/'operation_profile.json'
        step=run_step(ROOT,out,'Integrated operation benchmark',
                      [py,'-m','benchmarks.integrated_v0111.compare','--runs',str(args.runs),
                       '--warmup',str(args.warmup),'--large-bytes',str(args.large_bytes),'--out',str(raw)],
                      args.timeout)
        if step['status']=='PASS':
            try:
                benchmark=json.loads(raw.read_text()); violations=check_benchmark(benchmark)
                if violations:
                    step['status']='FAIL';step['reason']='; '.join(violations)
            except (ValueError,OSError,KeyError,TypeError) as e:
                step['status']='FAIL';step['reason']='invalid_benchmark_json:'+type(e).__name__
        checks.append(step)
    else:
        checks.append(skipped('Integrated operation benchmark','quick mode omits quantitative benchmark',required=False))
    review=check_releasability(ROOT)
    failures=[c for c in checks if c['required'] and c['status']!='PASS']
    report={'schema':'caaif-release-validation/v1','timestamp_utc':stamp(),
            'environment':{'python':sys.version.split()[0], 'interpreter':py, 'platform':platform.platform()},
            'mode':args.mode,'checks':checks,'benchmark':benchmark,
            'release_review':review,
            'automated_validation':'PASS' if not failures else 'FAIL',
            'release_status':'NOT_RELEASE_APPROVED',
            'notes':'A passing pipeline is not a claim of complete security, A2A equivalence, or public-release readiness.'}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (out/'report.md').write_text(write_markdown(report),encoding='utf-8')
    print('\nCAAIF VALIDATION '+report['automated_validation']+' | PUBLIC RELEASE REVIEW OPEN',flush=True)
    print('Report: '+str(out/'report.md'),flush=True)
    print('Structured data: '+str(out/'report.json'),flush=True)
    if failures:
        for c in failures: print('REQUIRED CHECK NOT PASSED: '+c['name']+' — '+c.get('reason',''),flush=True)
    return 1 if failures else 0


if __name__=='__main__':
    sys.exit(main())
