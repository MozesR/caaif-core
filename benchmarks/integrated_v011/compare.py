"""Measure four-hop CAAIF Controller + independent Context Provider + HTTP agents.

Includes POST/GET request wire bytes (headers + JSON bodies) and response JSON
body bytes from all client processes. Response headers, TCP/IP and TLS are NOT
measured. All application agents and Context Provider are real separate OS
processes; Controller + relay are in one trusted coordinator process.

This is not a fair A2A or ungoverned HTTP performance comparison.
"""
from __future__ import annotations
import argparse
import json
import multiprocessing as mp
import os
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmarks.integrated_v011.wire_meter import install, uninstall
from caaif_core.local import Denied
from caaif_core.provider_dispatch_v010 import ProviderBackedController
from caaif_core.remote_provider_v09 import ContextProviderV09, ProviderClientV09
from caaif_core.http_transport import ContextRelay, HTTPTransport
from examples.sdk_integrated_remote_v010_demo import await_worker, free_port, read_json

PROFILE=ROOT/'examples'/'three-agent'
IDS={'conversational':'demo.agent.conversational','reasoning':'demo.agent.reasoning','task':'demo.agent.task'}

def provider_main(queue, credentials, metrics_path):
    os.environ['CAAIF_V011_METRICS_PATH']=metrics_path
    os.environ['CAAIF_V011_ROLE']='provider'
    install()
    provider=ContextProviderV09(credentials, authorize_read=lambda actor,ref,ver,scope,corr:
        actor in IDS.values() and ref.startswith('ctx:v011/') and corr.startswith('bench-v011-')
        and not ref.endswith('/denied'))
    queue.put(provider.url)
    try:
        provider.serve_forever()
    finally:
        provider.close()

def parse_metrics(path):
    kinds={}
    roles={}
    if not path.exists():
        return kinds, roles
    for line in path.read_text().splitlines():
        if line:
            event=json.loads(line)
            kinds[event['kind']]=kinds.get(event['kind'],0)+event['bytes']
            per=roles.setdefault(event['role'],{})
            per[event['kind']]=per.get(event['kind'],0)+event['bytes']
    return kinds,roles

def run(runs=10,warmup=2,irrelevant_bytes=0,check_revocation=True):
    if not (1<=runs<=1000 and 0<=warmup<=100 and 0<=irrelevant_bytes<=500_000):
        raise ValueError('invalid_benchmark_arguments')
    ctx=mp.get_context('spawn')
    credentials={aid:secrets.token_urlsafe(32) for aid in IDS.values()}
    queue=ctx.Queue()
    with tempfile.TemporaryDirectory(prefix='caaif-v011-') as tmp:
        log=Path(tmp)/'wire.jsonl'
        os.environ['CAAIF_V011_METRICS_PATH']=str(log)
        os.environ['CAAIF_V011_ROLE']='controller'
        install()
        provider=ctx.Process(target=provider_main,args=(queue,credentials,str(log)),daemon=True)
        provider.start()
        workers=[]
        try:
            url=queue.get(timeout=8)
            clients={aid:ProviderClientV09(url,token) for aid,token in credentials.items()}
            contracts=[read_json(p) for p in sorted((PROFILE/'contracts').glob('*.json'))]
            core=ProviderBackedController(provider_clients=clients,profile=read_json(PROFILE/'profile.json'),
                contracts=contracts,policy=lambda r,c:r['correlation_id'].startswith('bench-v011-'),
                effect_policy=lambda r,c:r['input'].get('operation')=='create_outline')
            results=[]
            with ContextRelay() as relay:
                agents={}
                for role,aid in IDS.items():
                    port=free_port(); secret=secrets.token_urlsafe(32)
                    env=os.environ.copy();env['CAAIF_WORKER_SECRET']=secret
                    env['CAAIF_V011_ROLE']='worker-'+role
                    proc=subprocess.Popen([sys.executable,'-m','benchmarks.integrated_v011.worker_entry',role,str(port)],
                        cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    workers.append(proc)
                    await_worker(proc,port)
                    agents[role]=core.attach(aid,HTTPTransport(url=f'http://127.0.0.1:{port}',
                        recipient_id=aid,auth_token=secret,relay=relay))
                conv,reason,task=(agents[r] for r in ('conversational','reasoning','task'))
                # Do not include startup probes in measured calls.
                for i in range(warmup+runs):
                    log.write_text('')
                    start=time.perf_counter()
                    corr=f'bench-v011-{i}-{secrets.token_hex(6)}'
                    base='ctx:v011/'+corr+'/'
                    tail='x'*irrelevant_bytes
                    def publish(owner,name,scope,value,grants):
                        return core.publish_remote(owner,ref=base+name,version='v1',scope=scope,
                            correlation_id=corr,value=value,grants=grants)
                    r_intent=publish(conv,'intent','session.intent',
                        {'topic':'agent collaboration','private':tail}, {reason.agent_id:['topic']})
                    r1=core.dispatch(conv,core.new_request(conv,contract_id='demo.three-agent.intent.v1',
                        correlation_id=corr,context_refs=[r_intent],data={'intent':'Make an outline'}))
                    r_inst=publish(reason,'instructions','workspace.instructions',
                        {'topic':r1['output']['source_topic'],'private':tail}, {task.agent_id:['topic']})
                    decision=core.issue_decision(reason,correlation_id=corr,
                        contract_id='demo.three-agent.execute.v1',recipient_id=task.agent_id,
                        capability='task.execute',authorized=True)
                    r2=core.dispatch(reason,core.new_request(reason,
                        contract_id='demo.three-agent.execute.v1',correlation_id=corr,
                        context_refs=[r_inst],decision_ref=decision,
                        idempotency_key='v011-'+corr,data={'operation':'create_outline'}))
                    r_receipt=publish(task,'receipt','task.receipt',
                        {'points':r2['output']['points'],'private':tail}, {reason.agent_id:['points']})
                    r3=core.dispatch(task,core.new_request(task,contract_id='demo.three-agent.report.v1',
                        correlation_id=corr,context_refs=[r_receipt],data={'receipt_id':'receipt-001'}))
                    r_summary=publish(reason,'summary','workspace.summary',
                        {'points':r3['output']['summary_points'],'private':tail}, {conv.agent_id:['points']})
                    r4=core.dispatch(reason,core.new_request(reason,
                        contract_id='demo.three-agent.response.v1',correlation_id=corr,
                        context_refs=[r_summary],data={'style':'concise'}))
                    assert r4['output']['message']=='Here is your outline: What it is; How it works; Why it matters'
                    elapsed=(time.perf_counter()-start)*1000
                    # Count *successful* handoff traffic only. The subsequent
                    # adversarial revocation probe is tested but NOT counted
                    # as ordinary workflow cost.
                    kinds,roles=parse_metrics(log)
                    if i>=warmup:
                        results.append({'ms':elapsed,**kinds,'roles':roles})
                    if check_revocation:
                        clients[conv.agent_id].revoke(ref=r_intent['ref'],correlation_id=corr)
                        try:
                            core.dispatch(conv,core.new_request(conv,
                                contract_id='demo.three-agent.intent.v1',correlation_id=corr,
                                context_refs=[r_intent],data={'intent':'Make an outline'}))
                        except Denied as exc:
                            assert exc.code=='provider_context_denied'
                        else:
                            raise AssertionError('revocation_not_enforced')
                    assert sum(e['event']=='completed' for e in core.events)>=4*(i+1)
                mean=lambda key:statistics.mean(x.get(key,0) for x in results)
                reported={
                    'runs':runs,'warmup':warmup,'irrelevant_bytes_per_publication':irrelevant_bytes,
                    'mean_ms':round(mean('ms'),3),
                    'p50_ms':round(statistics.median(x['ms'] for x in results),3),
                    'p95_ms':round(sorted(x['ms'] for x in results)[max(0,__import__('math').ceil(.95*runs)-1)],3),
                    'http_requests':round(mean('http_request'),2),
                    'request_wire_bytes':round(mean('request_wire_bytes'),1),
                    'response_body_bytes':round(mean('response_body_bytes'),1),
                    'measured_combined_bytes':round(mean('request_wire_bytes')+mean('response_body_bytes'),1),
                    'revocation_tested':check_revocation
                }
                return reported
        finally:
            for proc in workers:
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
            if provider.is_alive():provider.terminate()
            provider.join(timeout=3)
            os.environ.pop('CAAIF_V011_METRICS_PATH',None)
            os.environ.pop('CAAIF_V011_ROLE',None)
            uninstall()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=int,default=10)
    p.add_argument('--warmup',type=int,default=2)
    p.add_argument('--large-bytes',type=int,default=18000)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    print(f'CAAIF Core SDK v0.11 Integrated Wire Benchmark | runs={args.runs} warmup={args.warmup}')
    results=[]
    for name,bytes_ in [('small',0),('large',args.large_bytes)]:
        result=run(runs=args.runs,warmup=args.warmup,irrelevant_bytes=bytes_)
        results.append({'case':name,**result})
        print(f"{name:5s} | {result['measured_combined_bytes']:.0f} B measured (requests incl. headers + response bodies) | {result['http_requests']:.0f} HTTP requests | p50={result['p50_ms']:.2f} ms | p95={result['p95_ms']:.2f} ms | revocation PASS")
    print('Counts successful handoffs: publication, provider authorization/read, worker dispatch, callback retrieval.')
    print('Each trial also tests revocation, excluded from ordinary workflow traffic and latency.')
    print('Excludes HTTP response headers, TCP/IP framing, TLS/WAN, model tokens and an equivalent A2A/control baseline.')
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps({'results':results,'note':'local wire benchmark, NOT A2A comparison'},indent=2))
        print('Results saved:',args.out)
    return results

if __name__=='__main__':main()
