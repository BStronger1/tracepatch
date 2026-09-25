"""Version 2: ten cookie contracts, including preserved metadata and jar state."""
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


    def test_standard_jar_policy_preserved(self):
        from http.cookiejar import DefaultCookiePolicy
        policy = DefaultCookiePolicy(blocked_domains=['example.invalid'])
        jar = CookieJar(policy=policy)
        jar.set_cookie(create_cookie('token', 'one', domain='example.invalid'))
        original = requests.Request('GET', 'http://example.invalid/', cookies=jar).prepare()
        copied = original.copy()
        self.assertEqual(copied._cookies._policy.blocked_domains(), ('example.invalid',))
        self.assertEqual(original._cookies._policy.blocked_domains(), ('example.invalid',))

    def test_update_preserves_rfc2109(self):
        source = CookieJar()
        source.set_cookie(create_cookie('token', 'one', version=1, rfc2109=True))
        target = RequestsCookieJar()
        target.update(source)
        self.assertIs(list(target)[0].rfc2109, True)
        self.assertIs(list(source)[0].rfc2109, True)

    def test_subclass_required_constructor_and_state(self):
        class LabelledJar(CookieJar):
            def __init__(self, label):
                super().__init__()
                self.label = label
        jar = LabelledJar('retain-me')
        jar.set_cookie(create_cookie('token', 'one'))
        original = requests.Request('GET', 'http://example.invalid/', cookies=jar).prepare()
        copied = original.copy()
        self.assertIs(type(copied._cookies), LabelledJar)
        self.assertEqual(copied._cookies.label, 'retain-me')
        self.assertIsNot(list(copied._cookies)[0], list(original._cookies)[0])
        copied._cookies.clear()
        self.assertEqual(len(list(original._cookies)), 1)

    def test_cookie_metadata_survives_prepared_copy(self):
        jar = RequestsCookieJar()
        cookie = create_cookie('token', 'one', domain='.example.invalid', path='/sub',
            version=1, rfc2109=True, secure=True, expires=2000000000,
            discard=False, comment='retain-comment', comment_url='https://example.invalid/policy',
            rest={'HttpOnly': None, 'Extra': 'retain-extra'})
        jar.set_cookie(cookie)
        original = requests.Request('GET', 'https://example.invalid/sub', cookies=jar).prepare()
        copied = list(original.copy()._cookies)[0]
        for field in ('name', 'value', 'domain', 'path', 'version', 'rfc2109', 'secure',
                      'expires', 'discard', 'comment', 'comment_url', '_rest'):
            with self.subTest(field=field):
                self.assertEqual(getattr(copied, field), getattr(cookie, field))
        self.assertIsNot(copied, cookie)



if __name__ == '__main__':
    unittest.main(verbosity=2)
