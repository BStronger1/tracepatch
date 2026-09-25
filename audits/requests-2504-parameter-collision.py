"""Post-hoc diagnostic, added after seeing the patch; NOT a frozen study test.

The candidate introduces populate_history as an internal keyword. It was not
reserved by the original Session.send API, so custom adapters may use that name.
"""
import unittest
import requests
from requests.adapters import BaseAdapter


class Raw:
    def release_conn(self):
        pass


class Transport(BaseAdapter):
    def __init__(self):
        self.seen = []

    def send(self, request, **kwargs):
        self.seen.append(kwargs)
        response = requests.Response()
        response.request, response.url = request, request.url
        response.status_code = 302 if len(self.seen) == 1 else 200
        response.headers['Location'] = '/end'
        response._content, response._content_consumed = b'ok', True
        response.raw = Raw()
        return response

    def close(self):
        pass


class ParameterCollision(unittest.TestCase):
    def test_custom_parameter_name_is_not_newly_reserved(self):
        with requests.Session() as session:
            session.trust_env = False
            adapter = Transport()
            session.mount('http://', adapter)
            prepared = requests.Request('GET', 'http://example.invalid/start').prepare()
            session.send(prepared, populate_history='adapter-owned')
            self.assertEqual([opts.get('populate_history') for opts in adapter.seen],
                             ['adapter-owned', 'adapter-owned'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
