"""Visible offline reproduction derived from the public issue, not a gold fix."""
import requests


class OfflineSession(requests.Session):
    def send(self, request, **kwargs):
        print('Prepared method:', repr(request.method))
        assert request.method == 'GET', 'bytes GET must reach transport as text GET'
        response = requests.Response()
        response.status_code = 200
        response._content = b'ok'
        response.request = request
        return response


session = OfflineSession()
session.trust_env = False
session.request(b'GET', 'http://example.invalid/')
print('Public issue reproduction passed')
