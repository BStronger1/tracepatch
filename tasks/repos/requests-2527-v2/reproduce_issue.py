"""Minimal public symptom: PreparedRequest.copy rejects a standard CookieJar."""
from http.cookiejar import CookieJar
import requests

jar = CookieJar()
jar.set_cookie(requests.cookies.create_cookie('session', 'original', domain='example.invalid'))
prepared = requests.Request('GET', 'http://example.invalid/', cookies=jar).prepare()
try:
    copied = prepared.copy()
except AttributeError as error:
    raise AssertionError('A standard CookieJar must be copyable') from error
assert copied._cookies is not prepared._cookies
assert [cookie.value for cookie in copied._cookies] == ['original']
print('Standard CookieJar copied')
