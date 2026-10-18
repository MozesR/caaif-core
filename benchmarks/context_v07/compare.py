"""CAAIF v0.7: full vs selected vs repeated ref vs cached ref vs delta.

Measurement: ACTUAL urllib JSON application-body bytes for worker invocations and
context relay retrieval. Context publication takes place IN PROCESS and is excluded.
Controller authorization and contracts run on every invocation. Cache lookups use
an IN-PROCESS trusted controller authorization callback; network validation of
cached context is intentionally not claimed. Synthetic deterministic fixture.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import secrets
import statistics
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from benchmarks.context_v05 import compare as prior
from caaif_core import http_transport as http
from caaif_core.context_reuse import VersionedContextCache, fingerprint, string_splice, canonical

MODES=('full', 'selected', 'reference', 'cached_reference', 'delta')
CASES=('tiny_selected','large_selected')


def fixture(case):
    if case == 'tiny_selected':
        relevant = 'Approved summary and context.'
    elif case == 'large_selected':
        relevant = 'Useful task context: ' + 'A'*3800 + '-end'
    else: raise ValueError('unknown_case')
    new_relevant = relevant[:-4] + 'NEW!'
    return {'needed':relevant, 'irrelevant':'X'*9000}, {'needed':new_relevant,'irrelevant':'X'*9000}


def measure(mode, case, runs, repeat, warmup, relay, url, token):
    doc0, doc1 = fixture(case)
    mid = repeat//2
    expected = [hashlib.sha256((doc0 if j < mid else doc1)['needed'].encode()).hexdigest()
                for j in range(repeat)]
    samples=[]
    holder={}
    agent_id=prior.IDS['reasoning']
    def authorize(recipient, ctx_ref, version, scope, corr):
        ctl=holder.get('core')
        item=ctl._contexts.get(ctx_ref) if ctl is not None else None
        return bool(item and not item['revoked'] and item['version']==version
                    and item['scope']==scope and corr==item['correlation_id']
                    and recipient in item['readers'])
    def handler(request, context):
        if request['context_refs']:
            ctx_ref=request['context_refs'][0]
            key=(agent_id,ctx_ref['ref'],ctx_ref['version'],ctx_ref['scope'],
                 request['correlation_id'])
            if mode=='reference':
                selected=context.resolve(ctx_ref['ref'])
            elif mode in ('cached_reference','delta'):
                selected=holder['cache'].get(*key)
                if selected is None:
                    change=request['input'].get('delta')
                    if change is not None and mode=='delta':
                        # Demo-specific trusted source comparison. Digest alone is
                        # NOT evidence of authorization or authenticity.
                        authorized_target=holder['core']._contexts[ctx_ref['ref']]['value']
                        if change['patch']['digest'] != fingerprint(authorized_target):
                            raise ValueError('delta_not_authoritative')
                        selected=holder['cache'].delta(agent_id,ctx_ref['ref'],change['base_version'],
                                             ctx_ref['version'],ctx_ref['scope'],
                                             request['correlation_id'],change['patch'])
                    else:
                        selected=context.resolve(ctx_ref['ref'])
                        holder['cache'].store(*key,selected)
            else:raise ValueError('invalid_mode')
            needed=selected['needed']
        else:
            needed=request['input']['document']['needed']
        return {'digest':hashlib.sha256(needed.encode()).hexdigest()}
    with http.AgentHTTPServer(agent_id=agent_id, auth_token=token,
                              handler=handler) as worker:
        for trial in range(runs+warmup):
            correlation=f'bench-v07-{case}-{mode}-{trial}'
            ref=f'ctx:v07/{case}/{trial}'
            holder['cache']=VersionedContextCache(authorize,max_entries=16)
            core,handles=prior.controller_and_agents(handler, relay, worker.url, token)
            holder['core']=core
            sender,recipient=handles['conversational'],handles['reasoning']
            versions=('v1','v2')
            refs=None
            if mode in ('reference','cached_reference','delta'):
                refs=core.put_context(sender, ref=ref,version=versions[0],
                                      scope='session.intent', value={'needed':doc0['needed']},
                                      readers={recipient.agent_id},correlation_id=correlation)
            ingest_model_bytes=0
            if refs is not None:
                ingest_model_bytes+=len(canonical({'needed':doc0['needed']}))
            metrics=prior.Measurements()
            with metrics.capture():
                start=time.perf_counter()
                for j in range(repeat):
                    current=(doc0 if j < mid else doc1)
                    change={}
                    if j == mid and refs is not None:
                        refs=core.put_context(sender,ref=ref,version=versions[1],
                                              scope='session.intent',value={'needed':doc1['needed']},
                                              readers={recipient.agent_id},correlation_id=correlation)
                        ingest_model_bytes+=len(canonical({'needed':doc1['needed']}))
                        if mode=='delta':
                            nxt={'needed':doc1['needed']}
                            change={'delta':{'base_version':'v1', 'patch':{
                                'changes':{'needed':string_splice(doc0['needed'],doc1['needed'])},
                                'digest':fingerprint(nxt)}}}
                    data=({'task':'extract', **change} if refs is not None else
                          {'task':'extract','document': current if mode=='full'
                           else {'needed':current['needed']}})
                    request=core.new_request(sender, contract_id=prior.CONTRACT_ID,
                                            correlation_id=correlation,
                                            context_refs=[refs] if refs is not None else [],data=data)
                    result=core.dispatch(sender,request)
                    assert result['status']=='completed' and result['output']['digest']==expected[j], 'mismatched_output'
                duration=(time.perf_counter()-start)*1000
            if trial>=warmup:
                stat=metrics.summary()
                expected_rpc=(repeat + (repeat if mode=='reference' else (1 if mode=='delta' else 2) if refs is not None else 0))
                assert stat['rpc']==expected_rpc, (mode,stat['rpc'],expected_rpc)
                samples.append((stat['bytes'],stat['rpc'],duration,ingest_model_bytes))
    return {'mode':mode, 'case':case, 'mean_body_bytes':statistics.mean(x[0] for x in samples),
            'mean_http_calls':statistics.mean(x[1] for x in samples),
            'mean_elapsed_ms':statistics.mean(x[2] for x in samples),
            'modeled_reference_ingestion_bytes':statistics.mean(x[3] for x in samples),
            'n':len(samples)}


def run(runs=20,repeat=6,warmup=3):
    if not (1<=runs<=1000 and 4<=repeat<=40 and repeat%2==0 and 0<=warmup<=100):
        raise ValueError('invalid_benchmark_parameters')
    results=[]
    token=secrets.token_urlsafe(32)
    with http.ContextRelay() as relay:
        for case in CASES:
            rows={}
            for mode in MODES:
                rows[mode]=measure(mode,case,runs,repeat,warmup,relay,None,token)
            results.extend(rows.values())
            print('\n'+case+' | '+str(repeat)+' handoffs, version changes after '+str(repeat//2))
            for mode,r in rows.items():
                print(f"  {mode:16s}: {r['mean_body_bytes']:8.0f} B | {r['mean_http_calls']:2.0f} HTTP | {r['mean_elapsed_ms']:.2f} ms | modeled ref ingestion={r['modeled_reference_ingestion_bytes']:.0f} B")
            base=rows['selected']['mean_body_bytes']
            diff=(base-rows['delta']['mean_body_bytes'])/base*100
            print(f'  delta vs selective-inline wire difference: {diff:+.1f}%')
    print('\nMeasured: loopback HTTP JSON body sizes and elapsed times for worker/context exchanges.')
    print('Not measured: publication/ingestion network, headers/TLS, remote policy authorization, token usage, A2A, live LLMs.')
    print('Modeled ingestion is NOT actual wire traffic; cache permission checks are in-process Controller lookups.')
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=int,default=20)
    parser.add_argument('--repeat',type=int,default=6)
    parser.add_argument('--warmup',type=int,default=3)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    print(f'CAAIF Core SDK v0.7 Context Reuse/Delta Benchmark | runs={args.runs} repeat={args.repeat} warmup={args.warmup}')
    results=run(args.runs,args.repeat,args.warmup)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps({'results':results},indent=2))
        print('Saved', args.out)
