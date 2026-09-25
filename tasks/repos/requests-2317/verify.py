"""Custom offline regression for issue 2316; no HTTP service or pytest required."""
import unittest
import requests
from requests.adapters import BaseAdapter


class RecordingTransport(BaseAdapter):
    def __init__(self):
        self.seen = []

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = 200 if request.method in ('GET', 'POST', 'HEAD', 'PATCH', 'DELETE') else 405
        response._content = b'ok'
        response.headers = {}
        return response

    def close(self):
        pass


class MethodContract(unittest.TestCase):
    def setUp(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.transport = RecordingTransport()
        self.session.mount('http://', self.transport)

    def tearDown(self):
        self.session.close()

    def test_bytes_get_issue_reproduction(self):
        response = self.session.request(b'GET', 'http://example.invalid/resource')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.transport.seen[-1][0].method, 'GET')

    def test_bytes_methods_and_case(self):
        for method in (b'get', b'POST', b'head', b'PATCH', b'DELETE'):
            with self.subTest(method=method):
                self.session.request(method, 'http://example.invalid/')
                self.assertEqual(self.transport.seen[-1][0].method, method.decode('ascii').upper())

    def test_text_methods_regression(self):
        for method in ('GET', 'get', 'POST', 'head', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                self.session.request(method, 'http://example.invalid/')
                self.assertEqual(self.transport.seen[-1][0].method, method.upper())

    def test_payload_headers_params_and_timeout_preserved(self):
        response = self.session.request(b'POST', 'http://example.invalid/resource',
            data={'value': 'hello'}, params={'page': '2'}, headers={'X-Trace': 'kept'}, timeout=7)
        prepared, options = self.transport.seen[-1]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(prepared.method, 'POST')
        self.assertEqual(prepared.body, 'value=hello')
        self.assertIn('page=2', prepared.url)
        self.assertEqual(prepared.headers['X-Trace'], 'kept')
        self.assertEqual(options['timeout'], 7)

    def test_text_convenience_method_preserved(self):
        response = self.session.get('http://example.invalid/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.transport.seen[-1][0].method, 'GET')


if __name__ == '__main__':
    unittest.main(verbosity=2)
