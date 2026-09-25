"""Independent in-memory redirect contracts; never supplied to the agent."""
import unittest
import requests
from requests.adapters import BaseAdapter


class Raw:
    def release_conn(self):
        pass


class Transport(BaseAdapter):
    def __init__(self, statuses):
        self.statuses, self.seen = statuses, []

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        r = requests.Response()
        r.request, r.url = request, request.url
        r.status_code = self.statuses[len(self.seen) - 1]
        r.headers['Location'] = '/hop' + str(len(self.seen))
        r._content, r._content_consumed = b'ok', True
        r.raw = Raw()
        return r

    def close(self):
        pass


class RedirectContract(unittest.TestCase):
    def run_case(self, statuses, method='GET', **options):
        with requests.Session() as session:
            session.trust_env = False
            adapter = Transport(statuses)
            session.mount('http://', adapter)
            prepared = requests.Request(method, 'http://example.invalid/start', data='payload').prepare()
            response = session.send(prepared, **options)
            return response, adapter.seen

    def test_custom_option_issue_reproduction(self):
        response, seen = self.run_case([302, 200], custom_trace='abc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([k.get('custom_trace') for _, k in seen], ['abc', 'abc'])

    def test_multiple_hops_and_options(self):
        marker = object()
        response, seen = self.run_case([302, 307, 200], extension=marker, feature=False, optional=None)
        self.assertEqual(len(response.history), 2)
        for _, options in seen:
            self.assertIs(options.get('extension'), marker)
            self.assertIn('optional', options)
            self.assertIsNone(options['optional'])
            self.assertIs(options.get('feature'), False)

    def test_standard_options_preserved(self):
        _, seen = self.run_case([307, 200], timeout=(2, 4), stream=True,
                                verify='test-ca', cert=('cert', 'key'), proxies={})
        for _, options in seen:
            self.assertEqual(options['timeout'], (2, 4))
            self.assertIs(options['stream'], True)
            self.assertEqual(options['verify'], 'test-ca')
            self.assertEqual(options['cert'], ('cert', 'key'))

    def test_redirect_disabled(self):
        response, seen = self.run_case([302], allow_redirects=False, custom_trace='abc')
        self.assertEqual(len(seen), 1)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('allow_redirects', seen[0][1])

    def test_post_302_conversion(self):
        _, seen = self.run_case([302, 200], method='POST', custom_trace='abc')
        self.assertEqual(seen[1][0].method, 'GET')
        self.assertIsNone(seen[1][0].body)
        self.assertEqual(seen[1][1].get('custom_trace'), 'abc')

    def test_post_307_preserves_body(self):
        _, seen = self.run_case([307, 200], method='POST', custom_trace='abc')
        self.assertEqual(seen[1][0].method, 'POST')
        self.assertEqual(seen[1][0].body, 'payload')
        self.assertEqual(seen[1][1].get('custom_trace'), 'abc')


if __name__ == '__main__':
    unittest.main(verbosity=2)
