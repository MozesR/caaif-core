"""CAAIF v0.9: provider and workers run in separate OS processes.

Demonstrates context-provider authorization, not yet live integration of
LocalController dispatch or production identities/policy providers.
"""
import multiprocessing as mp
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from caaif_core.remote_provider_v09 import ContextProviderV09, ProviderClientV09, ProviderError

REF = 'ctx:demo'
CORRELATION = 'session:001'
SCOPE = 'session.intent'


def _policy(actor, ref, version, scope, correlation_id):
    return actor in {'reasoning', 'task'} and ref == REF and scope == SCOPE and correlation_id == CORRELATION


def _provider(queue, credentials):
    server = ContextProviderV09(credentials, authorize_read=_policy)
    queue.put(server.url)
    try:
        server.serve_forever()
    finally:
        server.close()


def _worker(queue, url, token, action, version='v1'):
    client = ProviderClientV09(url, token)
    try:
        if action == 'publish':
            result = client.publish(ref=REF, version=version, scope=SCOPE,
                correlation_id=CORRELATION, value={
                    'needed':'summarize the analysis', 'instruction':'create three headings',
                    'private':'must not leave provider'},
                grants={'reasoning':['needed'], 'task':['instruction']})
        elif action == 'revoke':
            result = client.revoke(ref=REF, correlation_id=CORRELATION)
        else:
            result = client.read(ref=REF, version=version, scope=SCOPE,
                                 correlation_id=CORRELATION)
        queue.put(('ok', result))
    except ProviderError as exc:
        queue.put(('denied', exc.status, exc.code))


def main():
    ctx = mp.get_context('spawn')
    credentials = {role: secrets.token_urlsafe(32) for role in ('conversation', 'reasoning', 'task')}
    channel = ctx.Queue()
    provider = ctx.Process(target=_provider, args=(channel, credentials), daemon=True)
    provider.start()
    try:
        url = channel.get(timeout=10)
        def run(role, action, version='v1'):
            q = ctx.Queue()
            p = ctx.Process(target=_worker, args=(q, url, credentials[role], action, version))
            p.start()
            result = q.get(timeout=15)
            p.join(timeout=5)
            if p.exitcode != 0:
                raise RuntimeError('agent worker failed')
            return result
        assert run('conversation', 'publish')[0] == 'ok'
        reason = run('reasoning', 'read')
        task = run('task', 'read')
        assert reason[1]['value'] == {'needed': 'summarize the analysis'}
        assert task[1]['value'] == {'instruction': 'create three headings'}
        assert run('conversation', 'revoke')[0] == 'ok'
        after = run('reasoning', 'read')
        assert after == ('denied', 403, 'context_unavailable')
        print('CAAIF SDK v0.9 — Independent HTTP Context Provider')
        print('Provider: separate process; agents: separate worker processes')
        print('Conversational publishes context: PASS')
        print('Reasoning selective retrieval: PASS')
        print('Task selective retrieval: PASS')
        print('Retrieval after revocation rejected: PASS')
        print('Notes: loopback only; no LocalController dispatch integration or real LLMs')
    finally:
        provider.terminate()
        provider.join(timeout=5)


if __name__ == '__main__':
    main()
