"""CAAIF SDK v0.8: measured HTTP context-publication and policy-check cost.

This is a LOCALHOST *modeled architecture* experiment: a separate HTTP fixture
accepts publication traffic and simulates independent authorization. The actual
LocalController still performs its own mandatory policy and context checks.
The fixture is not a production context provider or independent policy engine.
No real LLM tokens, TLS, wire headers, WAN hops or A2A traffic are measured.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import secrets
import statistics
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from benchmarks.context_v05 import compare as prior
from benchmarks.context_v07 import compare as v07
from caaif_core import http_transport as http
from caaif_core.context_reuse import VersionedContextCache, fingerprint, string_splice, canonical

MODES = ('full', 'selected', 'reference', 'cached_reference', 'delta')
CASES = ('tiny_selected', 'large_selected')

class PublicationPolicyFixture:
    """Isolated authenticated HTTP meter and mock policy service.

    Stores a digest of each published value (not actual context). Its authorization
    predicate is a fixture, NOT a substitute for the LocalController decision.
    """
    def __init__(self, token: str):
        self.token = token
        self.records = {}
        self.lock = threading.RLock()
        self.thread = None
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def reply(self, code, data):
                payload = http._json(data)
                self.send_response(code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
            def do_POST(self):
                import hmac
                if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+fixture.token):
                    return self.reply(401, {'error':'unauthorized'})
                try:
                    data = http._read_json(self, http.MAX_CONTEXT_BODY)
                    if self.path == '/publish':
                        if set(data) != {'ref','version','scope','correlation','recipient','value'}:
                            raise ValueError('invalid_publish_fields')
                        key = (data['ref'],data['version'],data['scope'],data['correlation'],data['recipient'])
                        if not all(isinstance(v,str) and v for v in key) or not isinstance(data['value'],dict):
                            raise ValueError('invalid_publish_data')
                        with fixture.lock: fixture.records[key]=fingerprint(data['value'])
                        return self.reply(200,{'stored':True})
                    if self.path == '/authorize':
                        if set(data) != {'contract','caller','recipient','correlation','mode','ref','version','scope'}:
                            raise ValueError('invalid_authorize_fields')
                        allowed = (data['contract']==prior.CONTRACT_ID and
                                   data['caller']==prior.IDS['conversational'] and
                                   data['recipient']==prior.IDS['reasoning'] and
                                   isinstance(data['correlation'],str) and
                                   data['correlation'].startswith('bench-'))
                        if data['mode'] in ('reference','cached_reference','delta'):
                            key=(data['ref'],data['version'],data['scope'],data['correlation'],data['recipient'])
                            with fixture.lock: allowed=allowed and key in fixture.records
                        elif data['mode'] in ('full','selected'):
                            allowed=allowed and data['ref'] is None and data['version'] is None
                        else: allowed=False
                        return self.reply(200,{'allow':bool(allowed)})
                    if self.path == '/revoke':
                        if set(data) != {'ref','correlation'}: raise ValueError('invalid_revoke')
                        with fixture.lock:
                            for k in list(fixture.records):
                                if k[0]==data['ref'] and k[3]==data['correlation']:
                                    fixture.records.pop(k)
                        return self.reply(200, {'revoked':True})
                    return self.reply(404,{'error':'not_found'})
                except (ValueError,TypeError,KeyError,json.JSONDecodeError):
                    return self.reply(400, {'error':'invalid_request'})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def __enter__(self):
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); return self
    def __exit__(self,*_):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)
    def publish(self, ref, version, scope, corr, recipient, value):
        return http._send(self.url+'/publish',{'ref':ref,'version':version,'scope':scope,
                           'correlation':corr,'recipient':recipient,'value':value},self.token)
    def authorize(self, contract, caller, recipient, corr, mode, ref=None, version=None, scope=None):
        return http._send(self.url+'/authorize',{'contract':contract,'caller':caller,'recipient':recipient,
                           'correlation':corr,'mode':mode,'ref':ref,'version':version,'scope':scope},self.token)


def measure(mode, case, runs, repeat, warmup, relay, fixture, token):
    doc0,doc1=v07.fixture(case)
    mid=repeat//2
    expected=[hashlib.sha256((doc0 if j<mid else doc1)['needed'].encode()).hexdigest() for j in range(repeat)]
    samples=[]; holder={}; agent_id=prior.IDS['reasoning']
    def authorize_local(recipient,ctx_ref,version,scope,corr):
        core=holder.get('core'); item=core._contexts.get(ctx_ref) if core is not None else None
        return bool(item and not item['revoked'] and item['version']==version and item['scope']==scope
                    and corr==item['correlation_id'] and recipient in item['readers'])
    def handler(request, context):
        if request['context_refs']:
            ref=request['context_refs'][0]
            key=(agent_id,ref['ref'],ref['version'],ref['scope'],request['correlation_id'])
            if mode=='reference': selected=context.resolve(ref['ref'])
            else:
                selected=holder['cache'].get(*key)
                if selected is None:
                    change=request['input'].get('delta')
                    if change is not None and mode=='delta':
                        authorized=holder['core']._contexts[ref['ref']]['value']
                        if change['patch']['digest'] != fingerprint(authorized):
                            raise ValueError('delta_not_authoritative')
                        selected=holder['cache'].delta(agent_id,ref['ref'],change['base_version'],
                                  ref['version'],ref['scope'],request['correlation_id'],change['patch'])
                    else:
                        selected=context.resolve(ref['ref']); holder['cache'].store(*key,selected)
            needed=selected['needed']
        else: needed=request['input']['document']['needed']
        return {'digest': hashlib.sha256(needed.encode()).hexdigest()}
    with http.AgentHTTPServer(agent_id=agent_id,auth_token=token,handler=handler) as worker:
        for trial in range(runs+warmup):
            corr=f'bench-v08-{case}-{mode}-{trial}'
            ref=f'ctx:v08/{case}/{trial}'; scope='session.intent'; vers=('v1','v2')
            holder['cache']=VersionedContextCache(authorize_local,max_entries=16)
            core,handles=prior.controller_and_agents(handler,relay,worker.url,token)
            holder['core']=core
            sender,recipient=handles['conversational'],handles['reasoning']
            refs=None
            metrics=prior.Measurements()
            with metrics.capture():
                start=time.perf_counter()
                if mode in ('reference','cached_reference','delta'):
                    selected0={'needed':doc0['needed']}
                    refs=core.put_context(sender,ref=ref,version=vers[0],scope=scope,value=selected0,
                                          readers={recipient.agent_id},correlation_id=corr)
                    stored=fixture.publish(ref,vers[0],scope,corr,recipient.agent_id,selected0)
                    assert stored=={'stored':True}
                for j in range(repeat):
                    current=doc0 if j<mid else doc1; change={}
                    if j==mid and refs is not None:
                        selected1={'needed':doc1['needed']}
                        refs=core.put_context(sender,ref=ref,version=vers[1],scope=scope,value=selected1,
                                              readers={recipient.agent_id},correlation_id=corr)
                        assert fixture.publish(ref,vers[1],scope,corr,recipient.agent_id,selected1)=={'stored':True}
                        if mode=='delta':
                            change={'delta':{'base_version':'v1','patch':{
                                'changes':{'needed':string_splice(doc0['needed'],doc1['needed'])},
                                'digest':fingerprint(selected1)}}}
                    auth=fixture.authorize(prior.CONTRACT_ID,sender.agent_id,recipient.agent_id,corr,mode,
                                           refs['ref'] if refs else None,refs['version'] if refs else None,
                                           refs['scope'] if refs else None)
                    assert auth=={'allow':True}, 'remote_authorization_denied'
                    data=({'task':'extract',**change} if refs else {'task':'extract','document':
                          current if mode=='full' else {'needed':current['needed']}})
                    req=core.new_request(sender,contract_id=prior.CONTRACT_ID,correlation_id=corr,
                                         context_refs=[refs] if refs else [],data=data)
                    result=core.dispatch(sender,req)
                    assert result['status']=='completed' and result['output']['digest']==expected[j]
                elapsed_ms=(time.perf_counter()-start)*1000
            if trial>=warmup:
                stat=metrics.summary()
                extra=2 if refs is not None else 0
                context_reads=(repeat if mode=='reference' else 2 if mode=='cached_reference' else 1 if mode=='delta' else 0)
                expected_rpc=repeat*2+extra+context_reads  # workers + remote policy, plus pub and retrieval
                assert stat['rpc']==expected_rpc,(mode,stat['rpc'],expected_rpc)
                samples.append((stat['bytes'],stat['rpc'],elapsed_ms))
    return {'case':case,'mode':mode,'runs':runs,'repeat':repeat,
            'body_bytes':statistics.mean(s[0] for s in samples),
            'http_calls':statistics.mean(s[1] for s in samples),
            'mean_ms':statistics.mean(s[2] for s in samples)}


def run(runs=20,repeat=6,warmup=3,cases=CASES,modes=MODES):
    if not (1<=runs<=1000 and 4<=repeat<=40 and repeat%2==0 and 0<=warmup<=100):
        raise ValueError('invalid_benchmark_parameters')
    token=secrets.token_urlsafe(32); results=[]
    with http.ContextRelay() as relay,PublicationPolicyFixture(token) as fixture:
        for case in cases:
            rows={}
            for mode in modes:
                rows[mode]=measure(mode,case,runs,repeat,warmup,relay,fixture,token)
            results+=list(rows.values())
            print(f'\n{case} | {repeat} handoffs, one version update')
            for mode,r in rows.items():
                print(f"  {mode:16s} {r['body_bytes']:8.0f} B | {r['http_calls']:2.0f} HTTP | {r['mean_ms']:6.2f} ms")
            base=rows.get('selected')
            if base and 'delta' in rows:
                change=(base['body_bytes']-rows['delta']['body_bytes'])/base['body_bytes']*100
                print(f'  delta vs selective inline incl. publication+policy: {change:+.1f}%')
    print('\nIncluded: actual localhost HTTP JSON bodies for worker, retrieval, simulated publication and remote policy round trips.')
    print('Excluded: headers/TLS/WAN, real policy engine, network identity, model tokens, A2A, context discovery/selection cost.')
    print('The publication/policy service is a *mock fixture*; actual contract enforcement remains in LocalController.')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=int,default=20)
    p.add_argument('--repeat',type=int,default=6)
    p.add_argument('--warmup',type=int,default=3)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    print(f'CAAIF Core SDK v0.8 Publication/Policy Benchmark | runs={args.runs} repeat={args.repeat} warmup={args.warmup}')
    result=run(args.runs,args.repeat,args.warmup)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps({'results':result,'note':'localhost mock publication and policy service'},indent=2))
        print('Saved:',args.out)
