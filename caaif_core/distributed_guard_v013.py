"""CAAIF v0.13 distributed guarded reference (LOOPBACK RESEARCH ONLY).

Services run in independent processes. An LLM proposal cannot authorize itself;
controller grants are specific to action + parameters + context + identities;
execution is possible only through an authenticated tool gateway.

SECURITY LIMITS: static bearer service identities, shared-key proof token, and
in-memory permit/replay ledgers are deliberately NOT production security.
No TLS, SPIFFE, durable exactly-once, tenant isolation, or malicious OS-process
containment is provided. Legacy local SDK APIs remain untouched.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .guarded import ContextProvenance, GuardedLocalController, _digest
from .local import Denied
from .remote_provider_v09 import ProviderClientV09, ProviderError

MAX_BODY = 65536
TYP = 'CAAIF-v013-local-proof'  # NOT an interoperable token standard
AUD = 'caaif-tool-gateway-v013'


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _b64(binary):
    return base64.urlsafe_b64encode(binary).decode('ascii').rstrip('=')


def _unb64(value):
    if not isinstance(value, str) or not value or len(value) > 16384:
        raise ValueError('invalid_token')
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def sign_permit(claims, secret):
    wire = _b64(canonical(claims))
    mac = _b64(hmac.new(secret, wire.encode(), hashlib.sha256).digest())
    return wire + '.' + mac


def check_permit(token, secret, *, now=None):
    if not isinstance(token, str) or len(token) > 16384 or token.count('.') != 1:
        raise ValueError('malformed_permit')
    wire, signature = token.split('.')
    expected = _b64(hmac.new(secret, wire.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError('invalid_permit_signature')
    claims = json.loads(_unb64(wire))
    now = time.time() if now is None else now
    if (not isinstance(claims, dict) or claims.get('typ') != TYP or claims.get('aud') != AUD
        or not isinstance(claims.get('iat'), (int,float))
        or not isinstance(claims.get('exp'), (int,float))
        or claims['iat'] > now + 2 or claims['exp'] <= now
        or claims['exp'] - claims['iat'] > 61
        or not isinstance(claims.get('jti'), str) or not claims['jti']):
        raise ValueError('permit_invalid_or_expired')
    return claims


def _reply(handler, status, data):
    encoded = canonical(data)
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(encoded)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    try:
        handler.wfile.write(encoded)
    except (BrokenPipeError, ConnectionResetError):
        pass


def _read(handler):
    length = handler.headers.get('Content-Length', '')
    if not length.isdecimal() or not 0 < int(length) <= MAX_BODY:
        raise ValueError('invalid_content_length')
    body = json.loads(handler.rfile.read(int(length)))
    if not isinstance(body, dict):
        raise ValueError('json_object_required')
    return body


def _actor(header, credentials):
    if not isinstance(header, str) or not header.startswith('Bearer '):
        return None
    value = header[7:]
    for name, token in credentials.items():
        if hmac.compare_digest(value, token):
            return name
    return None


def post(url, path, body, token, *, timeout=4):
    if not url.startswith('http://127.0.0.1:') or not path.startswith('/'):
        raise ValueError('loopback_only')
    req = Request(url + path, data=canonical(body),
                  headers={'Content-Type':'application/json', 'Authorization':'Bearer '+token},
                  method='POST')
    try:
        with urlopen(req, timeout=timeout) as response:
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise ValueError('response_too_large')
            return json.loads(data)
    except HTTPError as err:
        try:
            payload = json.loads(err.read(MAX_BODY))
        except ValueError:
            payload = {'error':'upstream_error'}
        raise RemoteDenied(err.code, payload.get('error','upstream_error')) from None


class RemoteDenied(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f'{status}:{code}')


class GuardControllerV013:
    """Authenticates independent principals, reuses the v0.12 guarded policy.

    Controller is trusted; no effectful tool credentials exist in model agents.
    Context must already exist at separate provider, with a controller grant.
    """
    def __init__(self, *, provider_url, provider_token, credentials, signing_key,
                 profile, contracts, action_policy, port=0):
        if (len(set(credentials.values())) != len(credentials)
                or not {'host','reasoning','gateway'} <= set(credentials)
                or any(len(s)<24 for s in credentials.values())
                or len(signing_key)<32):
            raise ValueError('invalid_service_identity_config')
        self._tokens = dict(credentials)
        self._signing_key = signing_key.encode("utf-8") if isinstance(signing_key,str) else signing_key
        self._provider = ProviderClientV09(provider_url, provider_token)
        self._authority = object()
        self._core = GuardedLocalController(authority=self._authority,
                  action_policy=action_policy, policy_version='v013-policy',
                  profile=profile, contracts=contracts, policy=lambda req, contract: True)
        self._conv = self._core.attach(profile['roles']['conversational'][0], lambda req,ctx: {})
        self._reason = self._core.attach(profile['roles']['reasoning'][0], lambda req,ctx: {})
        self._task = self._core.attach(profile['roles']['task'][0], lambda req,ctx: {})
        self._issued = {}   # opaque signed permit by jti
        self._lock = threading.RLock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                if self.path == '/health':
                    return _reply(self, 200, {'status':'ok','service':'caaif-guarded-controller-v013'})
                return _reply(self, 404, {'error':'not_found'})
            def do_POST(self):
                roles = {'/trusted/context':{'host'}, '/trusted/intent':{'host'},
                         '/proposals':{'reasoning'}, '/trusted/authorize':{'host'},
                         '/trusted/revoke':{'host'}, '/trusted/disclose':{'host'}, '/introspect':{'gateway'},
                         '/trusted/events':{'host'}}
                if self.path not in roles:
                    return _reply(self, 404, {'error':'not_found'})
                actor = _actor(self.headers.get('Authorization'),server._tokens)
                if actor is None:
                    return _reply(self, 401, {'error':'unauthorized'})
                if actor not in roles[self.path]:
                    return _reply(self, 403, {'error':'role_not_permitted'})
                try:
                    body = _read(self)
                    with server._lock:
                        result = server._apply(self.path,body)
                    return _reply(self, 200, result)
                except (Denied, RemoteDenied, ProviderError) as exc:
                    code = exc.code if isinstance(exc,Denied) else (exc.code if isinstance(exc,RemoteDenied) else exc.code)
                    return _reply(self, 403, {'error':code})
                except (ValueError,TypeError,KeyError,OverflowError):
                    return _reply(self, 400, {'error':'invalid_request'})
                except (URLError,TimeoutError):
                    return _reply(self, 503, {'error':'provider_unavailable'})
                except Exception:
                    return _reply(self, 500, {'error':'controller_internal_error'})

        self._server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.url = f'http://127.0.0.1:{self._server.server_port}'
        self._thread=None

    def _apply(self,path,p):
        if path == '/trusted/context':
            if set(p) != {'descriptor','label'}:
                raise ValueError('invalid_context_registration')
            d, l = p['descriptor'],p['label']
            if not isinstance(d,dict) or set(d)!={'ref','version','scope','correlation_id'}:
                raise ValueError('invalid_context_descriptor')
            if not isinstance(l,dict) or set(l)!={'source_id','origin_trust','classification','allowed_purposes','allowed_recipients','allowed_actions'}:
                raise ValueError('invalid_context_label')
            # The provider verifies publication, version, and controller's read rights.
            self._provider.read(**d)
            label=ContextProvenance(source_id=l['source_id'],origin_trust=l['origin_trust'],
                classification=l['classification'],allowed_purposes=frozenset(l['allowed_purposes']),
                allowed_recipients=frozenset(l['allowed_recipients']),allowed_actions=frozenset(l['allowed_actions']))
            stored=self._core.put_context(self._conv,ref=d['ref'],version=d['version'],
                scope=d['scope'], correlation_id=d['correlation_id'],readers={self._task.agent_id,self._reason.agent_id},
                value={'external_provider':True})
            self._core.label_context(self._authority,ref=stored['ref'],version=stored['version'],label=label)
            return {'registered':True}
        if path == '/trusted/intent':
            if set(p) != {'intent_id','correlation_id','action','resource','parameters','purpose','context_refs'}:
                raise ValueError('invalid_intent')
            self._core.register_intent(self._authority,
                intent_id=p['intent_id'],correlation_id=p['correlation_id'],
                action=p['action'],resource=p['resource'],parameters=p['parameters'],
                purpose=p['purpose'],allowed_context_refs=p['context_refs'])
            return {'registered':True}
        if path == '/proposals':
            if set(p) != {'intent_id','contract_id','action','resource','parameters','purpose','context_refs'}:
                raise ValueError('invalid_proposal_fields')
            proposal_id=self._core.propose_effect(self._reason,**p)
            return {'proposal_id':proposal_id}
        if path == '/trusted/authorize':
            if set(p) != {'proposal_id'}:
                raise ValueError('invalid_authorize_fields')
            permit_id=self._core.authorize_effect(self._authority,p['proposal_id'])
            permit=self._core._permits[permit_id]
            proposal=self._core._proposals[permit['proposal_id']]
            intent=self._core._intents[permit['intent_id']]
            descriptor=intent['context_refs']
            # Recheck provider at authorization time (a local context mirror is not sufficient).
            for desc in descriptor:
                self._provider.read(ref=desc['ref'],version=desc['version'],scope=desc['scope'],
                                    correlation_id=intent['correlation_id'])
            exp=min(int(permit['expires'].timestamp()),int(time.time())+30)
            claims={'typ':TYP,'aud':AUD,'jti':permit_id,
                'iss':'caaif-guarded-controller-v013','sub':self._task.agent_id,
                'reasoning_agent':permit['issuer'],'contract_id':permit['contract_id'],
                'contract_version':permit['contract_version'],'intent_id':permit['intent_id'],
                'correlation_id':permit['correlation_id'],'action':permit['action'],
                'resource':permit['resource'],'parameters_hash':permit['parameters_hash'],
                'purpose':permit['purpose'],'context_refs':copy.deepcopy(descriptor),
                'policy_version':permit['policy_version'],'iat':int(time.time()),'exp':exp}
            signed=sign_permit(claims,self._signing_key)
            self._issued[permit_id]=signed
            return {'permit':signed,'expires_at':exp}
        if path == '/introspect':
            if set(p) != {'permit'}:
                raise ValueError('invalid_introspect')
            claims=check_permit(p['permit'],self._signing_key)
            permit=self._core._permits.get(claims['jti'])
            if not permit or claims['jti'] in self._core._revoked_decisions:
                raise Denied('permit_revoked_or_unknown')
            if not hmac.compare_digest(self._issued.get(claims['jti'],''),p['permit']):
                raise Denied('permit_not_current')
            if permit['expires'] <= self._core._clock() or permit['policy_version'] != self._core._policy_version:
                raise Denied('permit_expired_or_policy_changed')
            self._core._validated_proposal(self._core._proposals[permit['proposal_id']])
            for desc in claims['context_refs']:
                self._provider.read(ref=desc['ref'],version=desc['version'],scope=desc['scope'],
                                    correlation_id=claims['correlation_id'])
            return {'active':True,'jti':claims['jti']}
        if path == '/trusted/disclose':
            if set(p) != {'context_refs','recipient','purpose','correlation_id'}:
                raise ValueError('invalid_disclosure_request')
            for desc in p['context_refs']:
                self._provider.read(ref=desc['ref'],version=desc['version'],scope=desc['scope'],
                                    correlation_id=p['correlation_id'])
            self._core.authorize_disclosure(self._authority,
                context_refs=p['context_refs'],recipient=p['recipient'],purpose=p['purpose'])
            return {'authorized':True}
        if path == '/trusted/revoke':
            if set(p) != {'permit_id'}:
                raise ValueError('invalid_revoke')
            self._core.revoke_decision(p['permit_id'])
            return {'revoked':True}
        if path == '/trusted/events':
            if p:
                raise ValueError('invalid_events_request')
            return {'events':copy.deepcopy(self._core.events)}
        raise ValueError('invalid_endpoint')

    def serve_forever(self):
        self._server.serve_forever()
    def start(self):
        self._thread=threading.Thread(target=self._server.serve_forever,daemon=True)
        self._thread.start()
        return self
    def close(self):
        self._server.shutdown();self._server.server_close()
        if self._thread: self._thread.join(timeout=3)


class GuardedToolGatewayV013:
    """A separate authenticated enforcement point with no agent-supplied tools."""
    def __init__(self, *, credentials, signing_key, controller_url, controller_token,
                 provider_url, provider_token, tools, task_principal, port=0):
        if ('task' not in credentials or not len(credentials['task'])>=24 or len(signing_key)<32
                or not isinstance(tools,dict) or not tools or not all(callable(f) for f in tools.values())
                or not isinstance(task_principal,str) or not task_principal):
            raise ValueError('invalid_tool_gateway_configuration')
        self._tokens=dict(credentials)
        self._key=signing_key.encode("utf-8") if isinstance(signing_key,str) else signing_key
        self._controller_url=controller_url
        self._controller_token=controller_token
        self._provider=ProviderClientV09(provider_url,provider_token)
        self._tools=dict(tools)
        self._task_principal=task_principal
        self._seen=set()
        self._lock=threading.RLock()
        gateway=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args): pass
            def do_GET(self):
                if self.path=='/health':return _reply(self,200,{'status':'ok','service':'caaif-tool-gateway-v013'})
                return _reply(self,404,{'error':'not_found'})
            def do_POST(self):
                if self.path!='/execute':return _reply(self,404,{'error':'not_found'})
                actor=_actor(self.headers.get('Authorization'),gateway._tokens)
                if actor is None:return _reply(self,401,{'error':'unauthorized'})
                if actor!='task':return _reply(self,403,{'error':'role_not_permitted'})
                try:
                    data=_read(self)
                    with gateway._lock:
                        result=gateway._execute(data)
                    return _reply(self,200,result)
                except RemoteDenied as exc:
                    return _reply(self,403,{'error':'controller_denied','reason':exc.code})
                except (ProviderError,Denied):
                    return _reply(self,403,{'error':'context_or_policy_denied'})
                except ValueError as exc:
                    return _reply(self,403,{'error':str(exc)[:80]})
                except (URLError,TimeoutError):
                    return _reply(self,503,{'error':'verification_unavailable'})
                except Exception:
                    return _reply(self,500,{'error':'tool_outcome_uncertain'})
        self._server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.url=f'http://127.0.0.1:{self._server.server_port}'
        self._thread=None

    def _execute(self,body):
        if set(body)!={'permit','action_request'} or not isinstance(body['action_request'],dict):
            raise ValueError('invalid_execution_request')
        claims=check_permit(body['permit'],self._key)
        if claims.get('sub') != self._task_principal:
            raise ValueError('permit_subject_mismatch')
        request=body['action_request']
        if (set(request)!={'action','resource','parameters','purpose','intent_id'}
                or any(request.get(field)!=claims[field] for field in ('action','resource','purpose','intent_id'))
                or _digest(request.get('parameters'))!=claims['parameters_hash']):
            raise ValueError('action_binding_mismatch')
        if claims['jti'] in self._seen:
            raise ValueError('replay_denied')
        introspection=post(self._controller_url,'/introspect',{'permit':body['permit']},self._controller_token)
        if introspection != {'active':True,'jti':claims['jti']}:
            raise ValueError('introspection_mismatch')
        for desc in claims['context_refs']:
            # Context Provider performs independent grant+policy check at use.
            self._provider.read(ref=desc['ref'],version=desc['version'],scope=desc['scope'],
                                correlation_id=claims['correlation_id'])
        operation=self._tools.get(claims['action'])
        if operation is None:
            raise ValueError('unregistered_tool')
        # Single-use within process lifetime. On uncertain tool outcomes, do NOT retry.
        self._seen.add(claims['jti'])
        answer=operation(claims['resource'],copy.deepcopy(request['parameters']))
        return {'status':'completed','result':answer,'action_id':claims['jti']}

    def start(self):
        self._thread=threading.Thread(target=self._server.serve_forever,daemon=True)
        self._thread.start(); return self
    def close(self):
        self._server.shutdown();self._server.server_close()
        if self._thread:self._thread.join(timeout=3)
    def serve_forever(self):
        self._server.serve_forever()
