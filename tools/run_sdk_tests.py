#!/usr/bin/env python3
"""Run CAAIF SDK test modules in isolated subprocesses, with bounded timeouts.

Several SDK fixtures create local HTTP services; process isolation prevents one
module's lingering test threads or sockets from affecting the next module.
This test runner does not interpret any timeout/skip as a pass.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=75)
    parser.add_argument('--out', type=Path, default=Path('validation_reports/rc1'))
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error('timeout must be positive')
    dest = args.out if args.out.is_absolute() else ROOT / args.out
    dest.mkdir(parents=True, exist_ok=True)
    tests = sorted((ROOT / 'sdk_tests').glob('test_*.py'))
    if not tests:
        print('FAIL: No SDK test modules found')
        return 2
    total = 0
    outcomes = []
    for path in tests:
        cmd = [sys.executable, '-m', 'unittest', 'discover', '-s', 'sdk_tests', '-p', path.name, '-v']
        started = monotonic()
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=args.timeout)
            log = proc.stdout + '\n' + proc.stderr
            match = re.search(r'Ran (\d+) tests? in ', log)
            count = int(match.group(1)) if match else 0
            ok = proc.returncode == 0 and bool(re.search(r'^OK\s*$', log, re.M)) and count > 0
            reason = '' if ok else f'exit_code={proc.returncode}'
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or b''
            err = exc.stderr or b''
            log = (out.decode('utf-8', 'replace') if isinstance(out, bytes) else out)
            log += '\n' + (err.decode('utf-8', 'replace') if isinstance(err, bytes) else err)
            ok = False
            count = 0
            reason = f'timeout_after_{args.timeout}s'
        duration = round(monotonic()-started, 2)
        (dest / f'{path.stem}.log').write_text(log, encoding='utf-8')
        outcomes.append({'suite': path.name, 'result': 'PASS' if ok else 'FAIL',
                         'tests': count, 'duration_s': duration, 'reason': reason})
        print(f'{path.stem}: {"PASS" if ok else "FAIL"} ({count} tests, {duration:.1f}s){" "+reason if reason else ""}', flush=True)
        if ok:
            total += count
    status = 'PASS' if all(r['result'] == 'PASS' for r in outcomes) else 'FAIL'
    record = {'result': status, 'total_tests_passed': total, 'suite_count': len(outcomes),
              'suites': outcomes, 'test_runner': sys.executable}
    (dest/'sdk_summary.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'CAAIF RC1 SDK TESTS: {status} | {total} passed across {len(outcomes)} independent test modules', flush=True)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
