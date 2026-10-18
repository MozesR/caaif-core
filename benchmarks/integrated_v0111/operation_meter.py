"""Opt-in operation-level HTTP meter: stage labels, counts and bytes only.

No request paths, credentials, context values, URLs, payloads or headers are logged.
Reports HTTP request bytes including client request headers, and response *body*
bytes. Response headers, TCP/IP and TLS are excluded.
"""
from __future__ import annotations
import http.client
import json
import os
import time

_INSTALLED = False
_ORIGINAL_PUTREQUEST = http.client.HTTPConnection.putrequest
_ORIGINAL_SEND = http.client.HTTPConnection.send
_ORIGINAL_GETRESPONSE = http.client.HTTPConnection.getresponse
_ORIGINAL_READ = http.client.HTTPResponse.read

_STAGE_BY_PATH = {
    '/publish': 'publication',
    '/read': 'provider_read_and_auth',
    '/invoke': 'worker_dispatch',
    '/context/resolve': 'callback_retrieval',
}

def _emit(kind: str, n: int, stage: str):
    path = os.environ.get('CAAIF_V011_METRICS_PATH')
    if not path or not n:
        return
    event = {'role': os.environ.get('CAAIF_V011_ROLE', 'runner'),
             'stage': stage, 'kind': kind, 'bytes': n}
    payload = (json.dumps(event, separators=(',', ':')) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)

def _putrequest(self, method, url, *args, **kwargs):
    # Only store a fixed label; URLs and query parameters are never logged.
    path = url.split('?', 1)[0]
    self._caaif_meter_stage = _STAGE_BY_PATH.get(path, 'other')
    self._caaif_meter_start = time.perf_counter()
    return _ORIGINAL_PUTREQUEST(self, method, url, *args, **kwargs)

def _send(self, data):
    stage = getattr(self, '_caaif_meter_stage', 'other')
    if isinstance(data, (bytes, bytearray, memoryview)):
        _emit('request_wire_bytes', len(data), stage)
        if data[:5] == b'POST ' or data[:4] == b'GET ':
            _emit('http_request', 1, stage)
    return _ORIGINAL_SEND(self, data)

def _getresponse(self, *args, **kwargs):
    response = _ORIGINAL_GETRESPONSE(self, *args, **kwargs)
    response._caaif_meter_stage = getattr(self, '_caaif_meter_stage', 'other')
    response._caaif_meter_start = getattr(self, '_caaif_meter_start', None)
    return response

def _read(self, amt=None):
    data = _ORIGINAL_READ(self, amt)
    if isinstance(data, bytes):
        stage = getattr(self, '_caaif_meter_stage', 'other')
        _emit('response_body_bytes', len(data), stage)
        if self.isclosed() and not getattr(self, '_caaif_meter_timed', False):
            self._caaif_meter_timed = True
            start = getattr(self, '_caaif_meter_start', None)
            if start is not None:
                _emit('http_latency_us', round((time.perf_counter() - start) * 1_000_000), stage)
    return data

def install():
    global _INSTALLED
    if _INSTALLED:
        return
    http.client.HTTPConnection.putrequest = _putrequest
    http.client.HTTPConnection.send = _send
    http.client.HTTPConnection.getresponse = _getresponse
    http.client.HTTPResponse.read = _read
    _INSTALLED = True

def uninstall():
    global _INSTALLED
    if not _INSTALLED:
        return
    http.client.HTTPConnection.putrequest = _ORIGINAL_PUTREQUEST
    http.client.HTTPConnection.send = _ORIGINAL_SEND
    http.client.HTTPConnection.getresponse = _ORIGINAL_GETRESPONSE
    http.client.HTTPResponse.read = _ORIGINAL_READ
    _INSTALLED = False
