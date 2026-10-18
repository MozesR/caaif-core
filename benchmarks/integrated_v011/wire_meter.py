"""Research-only loopback HTTP wire meter. Never logs credentials, URLs or payloads.
Counts bytes supplied to socket transport and response body reads, not TLS and
not full response headers. It is deliberately opt-in; no SDK monkeypatch.
"""
from __future__ import annotations
import http.client
import json
import os
import threading

_INSTALLED = False
_ORIGINAL_SEND = http.client.HTTPConnection.send
_ORIGINAL_READ = http.client.HTTPResponse.read
_LOCAL = threading.local()

def _emit(kind: str, n: int):
    p = os.environ.get('CAAIF_V011_METRICS_PATH')
    if not p or not n:
        return
    event = {'role':os.environ.get('CAAIF_V011_ROLE','runner'), 'kind':kind, 'bytes':n}
    data = (json.dumps(event,separators=(',',':'))+'\n').encode()
    fd = os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        os.write(fd,data)
    finally:
        os.close(fd)

def _send(self, data):
    n = len(data) if isinstance(data,(bytes,bytearray,memoryview)) else 0
    _emit('request_wire_bytes',n)
    if isinstance(data,(bytes,bytearray)) and (data.startswith(b'POST ') or data.startswith(b'GET ')):
        _emit('http_request',1)
    return _ORIGINAL_SEND(self,data)

def _read(self,amt=None):
    data = _ORIGINAL_READ(self,amt)
    if isinstance(data,bytes):
        _emit('response_body_bytes',len(data))
    return data

def install():
    global _INSTALLED
    if not _INSTALLED:
        http.client.HTTPConnection.send = _send
        http.client.HTTPResponse.read = _read
        _INSTALLED=True


def uninstall():
    """Restore standard client I/O after the benchmark (no suite-wide hooks)."""
    global _INSTALLED
    if _INSTALLED:
        http.client.HTTPConnection.send = _ORIGINAL_SEND
        http.client.HTTPResponse.read = _ORIGINAL_READ
        _INSTALLED = False
