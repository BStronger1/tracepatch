"""Minimal public symptom: custom adapter options disappear after a redirect."""
import requests
from requests.adapters import BaseAdapter


class Raw:
    def release_conn(self):
        pass


class Transport(BaseAdapter):
    def __init__(self):
        self.options = []

    def send(self, request, **kwargs):
        self.options.append(kwargs)
        response = requests.Response()
        response.request, response.url = request, request.url
        response.status_code = 302 if len(self.options) == 1 else 200
        response.headers['Location'] = '/end'
        response._content = b'ok'
        response._content_consumed = True
        response.raw = Raw()
        return response

    def close(self):
        pass


session = requests.Session()
session.trust_env = False
transport = Transport()
session.mount('http://', transport)
prepared = requests.Request('GET', 'http://example.invalid/start').prepare()
session.send(prepared, trace_option='retained')
assert len(transport.options) == 2
assert transport.options[1].get('trace_option') == 'retained', transport.options
print('Redirect option preserved')
