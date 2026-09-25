"""Post-hoc diagnostics after inspecting the two 1024-token patches.

Not part of the six frozen contracts or the study's primary outcome.
One candidate hardcodes rfc2109=False; both reset a standard jar's policy.
"""
import unittest
from http.cookiejar import CookieJar, DefaultCookiePolicy
import requests
from requests.cookies import RequestsCookieJar, create_cookie


class CookieFlags(unittest.TestCase):
    def test_standard_jar_copy_preserves_policy_settings(self):
        policy = DefaultCookiePolicy(blocked_domains=['example.invalid'])
        jar = CookieJar(policy=policy)
        jar.set_cookie(create_cookie('token', 'one', domain='example.invalid'))
        original = requests.Request('GET', 'http://example.invalid/', cookies=jar).prepare()
        copied = original.copy()
        self.assertEqual(original._cookies._policy.blocked_domains(), ('example.invalid',))
        self.assertEqual(copied._cookies._policy.blocked_domains(), ('example.invalid',))

    def test_update_preserves_rfc2109_flag(self):
        original = create_cookie('token', 'one', domain='example.invalid',
                                 version=1, rfc2109=True)
        source = CookieJar()
        source.set_cookie(original)
        copied = RequestsCookieJar()
        copied.update(source)
        actual = list(copied)[0]
        self.assertIs(original.rfc2109, True)
        self.assertIs(actual.rfc2109, True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
