"""Tests for LocalSignaling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from pyunifiapi._exceptions import SDPPollTimeoutError, SignalingError
from pyunifiapi._types import TurnCredentials
from pyunifiapi.signaling._local import LocalSignaling


@pytest.fixture
def mock_http() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def signaling(mock_http: AsyncMock) -> LocalSignaling:
    return LocalSignaling(http=mock_http, site='default')


class TestGetTurnCredentials:
    async def test_success(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            200,
            json={
                'data': [
                    {
                        'uris': ['stun:stun.example.com:3478', 'turn:turn.example.com:3478'],
                        'username': 'user123',
                        'password': 'pass456',
                    }
                ],
            },
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/sdn'),
        )

        creds = await signaling.get_turn_credentials()

        assert creds.stun_urls == ['stun:stun.example.com:3478']
        assert creds.turn_urls == ['turn:turn.example.com:3478']
        assert creds.turn_username == 'user123'
        assert creds.turn_password == 'pass456'
        mock_http.post.assert_called_with('/api/s/default/cmd/sdn', json={'cmd': 'get-turn-credentials'})

    async def test_failure(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            400,
            json={'meta': {'rc': 'error'}},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/sdn'),
        )

        with pytest.raises(SignalingError, match='Failed to get TURN'):
            await signaling.get_turn_credentials()


class TestBuildSshSession:
    async def test_success(self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials) -> None:
        mock_http.post.return_value = httpx.Response(
            200,
            json={'data': []},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        await signaling.build_ssh_session(
            mac='AA:BB:CC:DD:EE:FF',
            uuid='test-uuid',
            turn=turn_credentials,
            username='ubnt',
            password='ubnt',
        )

        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        payload = call_args.kwargs.get('json') or call_args[1].get('json') or call_args[0][1]
        assert payload['cmd'] == 'build-ssh-session'
        assert payload['mac'] == 'aa:bb:cc:dd:ee:ff'  # Lowercased
        assert payload['uuid'] == 'test-uuid'
        assert payload['stun'] == 'stun.example.com:3478'  # Protocol stripped
        assert payload['turn'] == 'turn.example.com:3478'  # Protocol stripped

    async def test_failure(self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials) -> None:
        mock_http.post.return_value = httpx.Response(
            500,
            json={'meta': {'rc': 'error'}},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        with pytest.raises(SignalingError, match='Failed to build SSH'):
            await signaling.build_ssh_session(
                mac='aa:bb:cc:dd:ee:ff',
                uuid='test-uuid',
                turn=turn_credentials,
            )


class TestPollSdpOffer:
    async def test_success_first_attempt(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            200,
            json={'data': [{'ssh_sdp_offer': 'v=0\r\nsome-sdp'}]},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        offer = await signaling.poll_sdp_offer(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid')

        assert offer == 'v=0\r\nsome-sdp'

    async def test_success_after_retries(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        empty_response = httpx.Response(
            200,
            json={'data': [{}]},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )
        offer_response = httpx.Response(
            200,
            json={'data': [{'ssh_sdp_offer': 'v=0\r\ndelayed-sdp'}]},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        mock_http.post.side_effect = [empty_response, empty_response, offer_response]

        offer = await signaling.poll_sdp_offer(
            mac='aa:bb:cc:dd:ee:ff',
            uuid='test-uuid',
            max_retries=5,
            interval=0.01,  # Fast for tests
        )

        assert offer == 'v=0\r\ndelayed-sdp'
        assert mock_http.post.call_count == 3

    async def test_timeout(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        empty_response = httpx.Response(
            200,
            json={'data': [{}]},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )
        mock_http.post.return_value = empty_response

        with pytest.raises(SDPPollTimeoutError, match='No SDP offer'):
            await signaling.poll_sdp_offer(
                mac='aa:bb:cc:dd:ee:ff',
                uuid='test-uuid',
                max_retries=3,
                interval=0.01,
            )

        assert mock_http.post.call_count == 3


class TestSendSdpAnswer:
    async def test_success(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            200,
            json={'data': []},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        await signaling.send_sdp_answer(
            mac='aa:bb:cc:dd:ee:ff',
            uuid='test-uuid',
            sdp_answer='v=0\r\nanswer-sdp',
        )

        payload = mock_http.post.call_args.kwargs.get('json') or mock_http.post.call_args[1].get('json')
        assert payload['cmd'] == 'ssh-sdp-answer'
        assert payload['sdpanswer'] == 'v=0\r\nanswer-sdp'


class TestCloseSshSession:
    async def test_success(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            200,
            json={'data': []},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr'),
        )

        await signaling.close_ssh_session(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid')

        payload = mock_http.post.call_args.kwargs.get('json') or mock_http.post.call_args[1].get('json')
        assert payload['cmd'] == 'close-ssh-session'
