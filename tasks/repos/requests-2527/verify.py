"""Cookie copy and mutation isolation contracts; no network or agent access."""
import unittest
from http.cookiejar import CookieJar
import requests
from requests.cookies import RequestsCookieJar, create_cookie


class CookieContract(unittest.TestCase):
    def prepared(self, jar_type):
        jar = jar_type()
        jar.set_cookie(create_cookie('token', 'one', domain='example.invalid', path='/'))
        jar.set_cookie(create_cookie('token', 'two', domain='example.invalid', path='/sub'))
        return requests.Request('POST', 'http://example.invalid/sub', cookies=jar,
                                data='payload', headers={'X-Trace': 'kept'}).prepare()

    def test_standard_cookiejar_issue_reproduction(self):
        original = self.prepared(CookieJar)
        try:
            copied = original.copy()
        except AttributeError as error:
            self.fail(str(error))
        self.assertIsNot(copied._cookies, original._cookies)
        self.assertEqual(len(list(copied._cookies)), 2)

    def test_standard_cookie_objects_are_independent(self):
        original = self.prepared(CookieJar)
        copied = original.copy()
        list(copied._cookies)[0].value = 'changed'
        self.assertEqual([c.value for c in original._cookies], ['one', 'two'])
        copied._cookies.clear()
        self.assertEqual(len(list(original._cookies)), 2)

    def test_requests_cookie_objects_are_independent(self):
        original = self.prepared(RequestsCookieJar)
        copied = original.copy()
        list(copied._cookies)[0].value = 'changed'
        self.assertEqual([c.value for c in original._cookies], ['one', 'two'])

    def test_update_does_not_share_cookie_objects(self):
        source = self.prepared(CookieJar)._cookies
        destination = RequestsCookieJar()
        destination.update(source)
        list(destination)[0].value = 'changed'
        self.assertEqual([c.value for c in source], ['one', 'two'])

    def test_scope_and_request_fields_preserved(self):
        original = self.prepared(RequestsCookieJar)
        copied = original.copy()
        self.assertEqual([(c.name, c.domain, c.path, c.value) for c in copied._cookies],
                         [(c.name, c.domain, c.path, c.value) for c in original._cookies])
        self.assertEqual((copied.method, copied.url, copied.body),
                         (original.method, original.url, original.body))
        copied.headers['X-Trace'] = 'changed'
        self.assertEqual(original.headers['X-Trace'], 'kept')

    def test_empty_and_absent_cookiejar(self):
        for jar in (CookieJar(), RequestsCookieJar(), None):
            prepared = requests.PreparedRequest()
            prepared._cookies = jar
            copied = prepared.copy()
            if jar is None:
                self.assertIsNone(copied._cookies)
            else:
                self.assertIsNot(copied._cookies, jar)
                self.assertEqual(list(copied._cookies), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
