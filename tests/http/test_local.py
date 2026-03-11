"""Tests for LocalHttpTransport."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pyunifiapi._exceptions import ApiConnectionError, AuthenticationError
from pyunifiapi._types import ControllerConfig
from pyunifiapi.http._local import LocalHttpTransport


@pytest.fixture
def config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password')


class TestLocalHttpTransport:
    async def test_login_success(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        mock_response = httpx.Response(
            200,
            json={'meta': {'rc': 'ok'}},
            headers={'x-csrf-token': 'test-csrf'},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            await transport.login()

            assert transport._authenticated is True
            assert transport._csrf_token == 'test-csrf'

    async def test_login_failure(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        mock_response = httpx.Response(
            401,
            json={'meta': {'rc': 'error', 'msg': 'api.err.Invalid'}},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            with pytest.raises(AuthenticationError, match='Login failed'):
                await transport.login()

    async def test_login_connection_error(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError('Connection refused'))
            mock_ensure.return_value = mock_client

            with pytest.raises(ApiConnectionError, match='Cannot connect'):
                await transport.login()

    async def test_request_auto_login(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        login_response = httpx.Response(
            200,
            json={'meta': {'rc': 'ok'}},
            headers={'x-csrf-token': 'csrf-123'},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )
        api_response = httpx.Response(
            200,
            json={'data': [{'name': 'test'}]},
            request=httpx.Request('GET', 'https://192.168.1.1:443/api/s/default/stat/device'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=login_response)
            mock_client.request = AsyncMock(return_value=api_response)
            mock_ensure.return_value = mock_client

            resp = await transport.get('/api/s/default/stat/device')

            # Should have auto-logged in first
            mock_client.post.assert_called_once()
            assert resp.json()['data'][0]['name'] == 'test'

    async def test_request_reauth_on_401(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        transport._authenticated = True

        login_response = httpx.Response(
            200,
            json={'meta': {'rc': 'ok'}},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )
        unauthorized_response = httpx.Response(
            401,
            json={'meta': {'rc': 'error'}},
            request=httpx.Request('GET', 'https://192.168.1.1:443/api/test'),
        )
        ok_response = httpx.Response(
            200,
            json={'data': []},
            request=httpx.Request('GET', 'https://192.168.1.1:443/api/test'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[unauthorized_response, ok_response])
            mock_client.post = AsyncMock(return_value=login_response)
            mock_ensure.return_value = mock_client

            resp = await transport.get('/api/test')

            assert resp.status_code == 200
            assert mock_client.post.call_count == 1  # Re-auth login

    async def test_base_url(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        assert transport.base_url == 'https://192.168.1.1:443'

    async def test_base_url_custom_port(self) -> None:
        config = ControllerConfig(host='10.0.0.1', username='admin', password='pass', port=8443)
        transport = LocalHttpTransport(config)
        assert transport.base_url == 'https://10.0.0.1:8443'

    async def test_login_with_2fa(self) -> None:
        config = ControllerConfig(host='192.168.1.1', username='admin', password='password', totp_secret='JBSWY3DPEHPK3PXP')
        transport = LocalHttpTransport(config)
        mock_response = httpx.Response(
            200,
            json={'meta': {'rc': 'ok'}},
            headers={'x-csrf-token': 'test-csrf'},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            await transport.login()

            # Verify the login payload included ubic_2fa_token
            call_kwargs = mock_client.post.call_args
            login_json = call_kwargs.kwargs.get('json') or call_kwargs[1].get('json')
            assert 'ubic_2fa_token' in login_json
            assert len(login_json['ubic_2fa_token']) == 6
            assert login_json['ubic_2fa_token'].isdigit()
            assert transport._authenticated is True

    async def test_login_without_2fa_no_token(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        mock_response = httpx.Response(
            200,
            json={'meta': {'rc': 'ok'}},
            headers={'x-csrf-token': 'test-csrf'},
            request=httpx.Request('POST', 'https://192.168.1.1:443/api/auth/login'),
        )

        with patch.object(transport, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_client

            await transport.login()

            # Verify no ubic_2fa_token when totp_secret is not set
            call_kwargs = mock_client.post.call_args
            login_json = call_kwargs.kwargs.get('json') or call_kwargs[1].get('json')
            assert 'ubic_2fa_token' not in login_json

    async def test_close(self, config: ControllerConfig) -> None:
        transport = LocalHttpTransport(config)
        mock_client = AsyncMock()
        transport._client = mock_client
        transport._authenticated = True

        await transport.close()

        mock_client.aclose.assert_called_once()
        assert transport._client is None
        assert transport._authenticated is False
