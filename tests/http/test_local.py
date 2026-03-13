"""Tests for LocalHttpTransport."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pyunifiapi._exceptions import ApiConnectionError, AuthenticationError
from pyunifiapi._types import ControllerConfig
from pyunifiapi.http._local import LocalHttpTransport

LOGIN_URL = 'https://192.168.1.1:443/api/auth/login'


def _ok_response(**kwargs) -> httpx.Response:
    return httpx.Response(200, json={'meta': {'rc': 'ok'}}, request=httpx.Request('POST', LOGIN_URL), **kwargs)


def _error_response(status: int = 401, **kwargs) -> httpx.Response:
    return httpx.Response(status, json={'meta': {'rc': 'error', 'msg': 'api.err.Invalid'}}, request=httpx.Request('POST', LOGIN_URL), **kwargs)


@pytest.fixture
def config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password')


@pytest.fixture
def config_2fa() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password', totp_secret='JBSWY3DPEHPK3PXP')


class TestLogin:
    async def test_success(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_ok_response(headers={'x-csrf-token': 'test-csrf'}))
            mock_ensure.return_value = mock_client

            await transport.login()

            assert transport._authenticated is True
            assert transport._csrf_token == 'test-csrf'

    async def test_failure(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_error_response())
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='Login failed'):
                await transport.login()

    async def test_connection_error(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError('Connection refused'))
            mock_ensure.return_value = mock_client

            with pytest.raises(ApiConnectionError, match='Cannot connect'):
                await transport.login()

    async def test_no_2fa_token_without_secret(self, config: ControllerConfig) -> None:
        """Without totp_secret, login sends no 2FA token fields."""
        transport = LocalHttpTransport(config)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_ok_response())
            mock_ensure.return_value = mock_client

            await transport.login()

            login_json = mock_client.post.call_args.kwargs.get('json') or mock_client.post.call_args[1].get('json')
            assert 'ubic_2fa_token' not in login_json
            assert 'token' not in login_json

    async def test_first_post_never_contains_2fa_token(self, config_2fa: ControllerConfig) -> None:
        """Even with totp_secret, the first POST never includes a 2FA token (auto-detect flow)."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_ok_response())
            mock_ensure.return_value = mock_client

            await transport.login()

            login_json = mock_client.post.call_args.kwargs.get('json') or mock_client.post.call_args[1].get('json')
            assert 'ubic_2fa_token' not in login_json
            assert 'token' not in login_json

    async def test_success_with_totp_secret_but_no_challenge(self, config_2fa: ControllerConfig) -> None:
        """If the controller returns 200 on first try, no 2FA retry happens even with totp_secret."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=_ok_response())
            mock_ensure.return_value = mock_client

            await transport.login()

            assert transport._authenticated is True
            assert mock_client.post.call_count == 1


class TestSso2fa:
    def _mfa_499_response(self, cookie: str = 'UBIC_2FA=abc123') -> httpx.Response:
        return httpx.Response(
            499,
            json={'data': {'mfaCookie': cookie}},
            request=httpx.Request('POST', LOGIN_URL),
        )

    async def test_sso_two_step_success(self, config_2fa: ControllerConfig) -> None:
        """SSO flow: first POST returns 499 with mfaCookie, second POST includes token."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(side_effect=[self._mfa_499_response(), _ok_response(headers={'x-csrf-token': 'csrf-sso'})])
            mock_ensure.return_value = mock_client

            await transport.login()

            assert transport._authenticated is True
            assert transport._csrf_token == 'csrf-sso'
            assert mock_client.post.call_count == 2

            # Second call should have 'token' field (SSO)
            second_call_json = mock_client.post.call_args_list[1].kwargs.get('json') or mock_client.post.call_args_list[1][1].get('json')
            assert 'token' in second_call_json
            assert len(second_call_json['token']) == 6
            assert second_call_json['token'].isdigit()

    async def test_sso_sets_mfa_cookie(self, config_2fa: ControllerConfig) -> None:
        """The mfaCookie from the 499 response is set on the HTTP client."""
        transport = LocalHttpTransport(config_2fa)
        cookies = httpx.Cookies()
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = cookies
            mock_client.post = AsyncMock(side_effect=[self._mfa_499_response('MY_COOKIE=secret_val'), _ok_response()])
            mock_ensure.return_value = mock_client

            await transport.login()

            assert cookies.get('MY_COOKIE') == 'secret_val'

    async def test_sso_missing_mfa_cookie(self, config_2fa: ControllerConfig) -> None:
        """499 response without mfaCookie raises AuthenticationError."""
        transport = LocalHttpTransport(config_2fa)
        resp_499 = httpx.Response(499, json={'data': {}}, request=httpx.Request('POST', LOGIN_URL))
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(return_value=resp_499)
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='missing or malformed mfaCookie'):
                await transport.login()

    async def test_sso_malformed_mfa_cookie(self, config_2fa: ControllerConfig) -> None:
        """499 response with mfaCookie missing '=' raises AuthenticationError."""
        transport = LocalHttpTransport(config_2fa)
        resp_499 = httpx.Response(499, json={'data': {'mfaCookie': 'no-equals-sign'}}, request=httpx.Request('POST', LOGIN_URL))
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(return_value=resp_499)
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='missing or malformed mfaCookie'):
                await transport.login()

    async def test_sso_unparseable_response(self, config_2fa: ControllerConfig) -> None:
        """499 response with non-JSON body raises AuthenticationError."""
        transport = LocalHttpTransport(config_2fa)
        resp_499 = httpx.Response(499, text='not json', request=httpx.Request('POST', LOGIN_URL))
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(return_value=resp_499)
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='unable to parse MFA response'):
                await transport.login()

    async def test_sso_second_post_fails(self, config_2fa: ControllerConfig) -> None:
        """If the second POST (with token) fails, AuthenticationError is raised."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(side_effect=[self._mfa_499_response(), _error_response()])
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='Login failed'):
                await transport.login()

    async def test_499_without_totp_secret_raises(self, config: ControllerConfig) -> None:
        """499 response without totp_secret configured raises AuthenticationError (can't complete 2FA)."""
        transport = LocalHttpTransport(config)
        resp_499 = httpx.Response(499, json={'data': {'mfaCookie': 'X=Y'}}, request=httpx.Request('POST', LOGIN_URL))
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=resp_499)
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='Login failed'):
                await transport.login()

    async def test_sso_connection_error_on_retry(self, config_2fa: ControllerConfig) -> None:
        """Connection error on SSO second POST raises ApiConnectionError."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.cookies = httpx.Cookies()
            mock_client.post = AsyncMock(side_effect=[self._mfa_499_response(), httpx.ConnectError('Connection lost')])
            mock_ensure.return_value = mock_client

            with pytest.raises(ApiConnectionError, match='Cannot connect'):
                await transport.login()


class TestLocal2fa:
    async def test_local_2fa_fallback(self, config_2fa: ControllerConfig) -> None:
        """Non-499 failure with totp_secret retries with ubic_2fa_token."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[_error_response(), _ok_response(headers={'x-csrf-token': 'csrf-local'})])
            mock_ensure.return_value = mock_client

            await transport.login()

            assert transport._authenticated is True
            assert mock_client.post.call_count == 2

            second_call_json = mock_client.post.call_args_list[1].kwargs.get('json') or mock_client.post.call_args_list[1][1].get('json')
            assert 'ubic_2fa_token' in second_call_json
            assert len(second_call_json['ubic_2fa_token']) == 6
            assert second_call_json['ubic_2fa_token'].isdigit()

    async def test_local_2fa_retry_fails(self, config_2fa: ControllerConfig) -> None:
        """If both first and retry POST fail, AuthenticationError is raised."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[_error_response(), _error_response()])
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='Login failed'):
                await transport.login()

    async def test_local_2fa_connection_error_on_retry(self, config_2fa: ControllerConfig) -> None:
        """Connection error on local 2FA retry raises ApiConnectionError."""
        transport = LocalHttpTransport(config_2fa)
        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[_error_response(), httpx.ConnectError('Connection lost')])
            mock_ensure.return_value = mock_client

            with pytest.raises(ApiConnectionError, match='Cannot connect'):
                await transport.login()


class TestRequest:
    async def test_auto_login(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        login_response = _ok_response(headers={'x-csrf-token': 'csrf-123'})
        api_response = httpx.Response(
            200, json={'data': [{'name': 'test'}]}, request=httpx.Request('GET', 'https://192.168.1.1:443/api/s/default/stat/device')
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=login_response)
            mock_client.request = AsyncMock(return_value=api_response)
            mock_ensure.return_value = mock_client

            resp = await transport.get('/api/s/default/stat/device')

            mock_client.post.assert_called_once()
            assert resp.json()['data'][0]['name'] == 'test'

    async def test_reauth_on_401(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        transport._authenticated = True

        login_response = _ok_response()
        unauthorized = httpx.Response(401, json={'meta': {'rc': 'error'}}, request=httpx.Request('GET', 'https://192.168.1.1:443/api/test'))
        ok = httpx.Response(200, json={'data': []}, request=httpx.Request('GET', 'https://192.168.1.1:443/api/test'))

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[unauthorized, ok])
            mock_client.post = AsyncMock(return_value=login_response)
            mock_ensure.return_value = mock_client

            resp = await transport.get('/api/test')

            assert resp.status_code == 200
            assert mock_client.post.call_count == 1


class TestMisc:
    async def test_base_url(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        assert transport.base_url == 'https://192.168.1.1:443'

    async def test_base_url_custom_port(self) -> None:
        config = ControllerConfig(host='10.0.0.1', username='admin', password='pass', port=8443)
        transport = LocalHttpTransport(config)
        assert transport.base_url == 'https://10.0.0.1:8443'

    async def test_close(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        mock_client = AsyncMock()
        transport._client = mock_client
        transport._authenticated = True

        await transport.close()

        mock_client.aclose.assert_called_once()
        assert transport._client is None
        assert transport._authenticated is False
