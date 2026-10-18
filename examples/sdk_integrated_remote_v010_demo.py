"""v0.10: Four authorized Three-Agent dispatches with external Context Provider.

Local controller and HTTP ContextRelay run in trusted coordinating process.
Provider lives in a separate OS process; each agent worker in a separate OS process.
No real LLM, A2A, WAN identity or production-grade security is implied.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core.local import Denied
from caaif_core.provider_dispatch_v010 import ProviderBackedController
from caaif_core.remote_provider_v09 import ContextProviderV09, ProviderClientV09
from caaif_core.http_transport import ContextRelay, HTTPTransport

PROFILE = ROOT / 'examples' / 'three-agent'
IDS = {'conversational':'demo.agent.conversational', 'reasoning':'demo.agent.reasoning', 'task':'demo.agent.task'}


def policy(actor, ref, version, scope, correlation_id):
    return actor in set(IDS.values()) and ref.startswith('ctx:integration/') and correlation_id == 'integration-001' and not ref.endswith('/policy-denied')


def provider_main(queue, credentials):
    provider = ContextProviderV09(credentials, authorize_read=policy)
    queue.put(provider.url)
    try:
        provider.serve_forever()
    finally:
        provider.close()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def await_worker(proc, port):
    limit=time.monotonic()+8
    while time.monotonic()<limit:
        if proc.poll() is not None:
            raise RuntimeError('worker_crashed')
        try:
            with urlopen(f'http://127.0.0.1:{port}/health',timeout=.2) as res:
                if json.load(res)['status']=='ok':
                    return
        except Exception:
            time.sleep(.05)
    raise TimeoutError('worker_not_ready')


def read_json(path):
    return json.loads(Path(path).read_text())


def main():
    ctx=mp.get_context('spawn')
    credentials={aid:secrets.token_urlsafe(32) for aid in IDS.values()}
    queue=ctx.Queue()
    provider=ctx.Process(target=provider_main,args=(queue,credentials),daemon=True)
    provider.start()
    procs=[]
    try:
        url=queue.get(timeout=8)
        clients={aid:ProviderClientV09(url,token) for aid,token in credentials.items()}
        contracts=[read_json(p) for p in sorted((PROFILE/'contracts').glob('*.json'))]
        core=ProviderBackedController(provider_clients=clients,profile=read_json(PROFILE/'profile.json'),
               contracts=contracts,policy=lambda r,c:r['correlation_id'].startswith('integration-'),
               effect_policy=lambda r,c:r['input'].get('operation')=='create_outline')
        with ContextRelay() as relay:
            agents={}
            for role,aid in IDS.items():
                port=free_port()
                secret=secrets.token_urlsafe(32)
                env=os.environ.copy()
                env['CAAIF_WORKER_SECRET']=secret
                proc=subprocess.Popen([sys.executable,str(ROOT/'examples'/'http_agent_worker.py'),role,str(port)],
                                      env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                procs.append(proc)
                await_worker(proc,port)
                agents[role]=core.attach(aid, HTTPTransport(url=f'http://127.0.0.1:{port}',
                    recipient_id=aid, auth_token=secret,relay=relay))
            conv,reason,task=(agents['conversational'],agents['reasoning'],agents['task'])
            corr='integration-001'
            intent=core.publish_remote(conv, ref='ctx:integration/intent', version='v1',scope='session.intent',
                correlation_id=corr,value={'topic':'agent collaboration','private':'do not send'},
                grants={reason.agent_id:['topic']})
            r1=core.dispatch(conv,core.new_request(conv,contract_id='demo.three-agent.intent.v1',
                correlation_id=corr,context_refs=[intent],data={'intent':'Make an outline'}))
            assert r1['output']['source_topic']=='agent collaboration'
            instruction=core.publish_remote(reason,ref='ctx:integration/instructions',version='v1',
                scope='workspace.instructions',correlation_id=corr,
                value={'topic':r1['output']['source_topic'],'private':'do not send'},
                grants={task.agent_id:['topic']})
            decision=core.issue_decision(reason,correlation_id=corr,contract_id='demo.three-agent.execute.v1',
                recipient_id=task.agent_id,capability='task.execute',authorized=True)
            r2=core.dispatch(reason,core.new_request(reason,contract_id='demo.three-agent.execute.v1',
                correlation_id=corr,context_refs=[instruction],decision_ref=decision,
                idempotency_key='integration-task-001',data={'operation':'create_outline'}))
            receipt=core.publish_remote(task,ref='ctx:integration/receipt',version='v1',scope='task.receipt',
                correlation_id=corr,value={'points':r2['output']['points'],'private':'do not send'},
                grants={reason.agent_id:['points']})
            r3=core.dispatch(task,core.new_request(task,contract_id='demo.three-agent.report.v1',
                correlation_id=corr,context_refs=[receipt],data={'receipt_id':'receipt-001'}))
            summary=core.publish_remote(reason,ref='ctx:integration/summary',version='v1',
                scope='workspace.summary',correlation_id=corr,
                value={'points':r3['output']['summary_points'],'private':'do not send'},
                grants={conv.agent_id:['points']})
            r4=core.dispatch(reason,core.new_request(reason,contract_id='demo.three-agent.response.v1',
                correlation_id=corr,context_refs=[summary],data={'style':'concise'}))
            assert r4['output']['message']=='Here is your outline: What it is; How it works; Why it matters'
            assert sum(x['event']=='completed' for x in core.events)==4
            assert sum(x['event']=='context_resolved' for x in core.events)==4
            # Verify independent provider access denial after revocation, not only local flags.
            revoked=core.publish_remote(conv,ref='ctx:integration/revoked',version='v1',
                scope='session.intent',correlation_id=corr,value={'topic':'private'},
                grants={reason.agent_id:['topic']})
            clients[conv.agent_id].revoke(ref=revoked['ref'],correlation_id=corr)
            try:
                core.dispatch(conv,core.new_request(conv,contract_id='demo.three-agent.intent.v1',
                    correlation_id=corr,context_refs=[revoked],data={'intent':'Analyze'}))
            except Denied as exc:
                assert exc.code=='provider_context_denied',str(exc)
            else:
                raise AssertionError('revocation_bypass')
            print('CAAIF Core SDK v0.10 — Integrated Controller + Independent Context Provider')
            print('Interaction Controller: contract and decision enforcement: PASS')
            print('Provider: separate process; agents: three separate HTTP processes')
            print('Authorized interactions: 4; context resolutions: 4')
            print('Provider field selection and retrieval-time authorization: PASS')
            print('Context revocation rejected by independent provider: PASS')
            print(r4['output']['message'])
            print('Research only: loopback, trusted coordinator; no WAN/LLM/A2A benchmark')
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)
        provider.terminate();provider.join(timeout=5)


if __name__=='__main__':
    main()
