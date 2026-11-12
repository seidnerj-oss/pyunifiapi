"""Tests for LocalSignaling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pyunifiapi._exceptions import SDPPollTimeoutError, SignalingError
from pyunifiapi._types import ControllerConfig, TurnCredentials
from pyunifiapi.models.message import Message
from pyunifiapi.signaling._local import LocalSignaling

DEVMGR_REQUEST = httpx.Request('POST', 'https://test/api/s/default/cmd/devmgr')


class FakeEventsWebSocket:
    """Stand-in for WebSocketClient: replays queued raw events, then blocks until closed."""

    instances: list[FakeEventsWebSocket] = []
    events: list[dict[str, Any]] = []
    end_stream = False
    connect_error: Exception | None = None
    log: list[str] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.closed = False
        FakeEventsWebSocket.instances.append(self)

    async def connect(self) -> None:
        FakeEventsWebSocket.log.append('ws-connect')
        if FakeEventsWebSocket.connect_error:
            raise FakeEventsWebSocket.connect_error

    async def listen(self) -> AsyncIterator[Message]:
        for raw in FakeEventsWebSocket.events:
            yield Message.from_raw(raw)
        if FakeEventsWebSocket.end_stream:
            return
        await asyncio.Event().wait()

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def fake_ws(monkeypatch: pytest.MonkeyPatch) -> type[FakeEventsWebSocket]:
    FakeEventsWebSocket.instances = []
    FakeEventsWebSocket.events = []
    FakeEventsWebSocket.end_stream = False
    FakeEventsWebSocket.connect_error = None
    FakeEventsWebSocket.log = []
    monkeypatch.setattr('pyunifiapi.signaling._local.WebSocketClient', FakeEventsWebSocket, raising=False)
    return FakeEventsWebSocket


@pytest.fixture
def mock_http(controller_config: ControllerConfig) -> AsyncMock:
    http = AsyncMock()
    http._config = controller_config
    http.get_cookies = MagicMock(return_value={'TOKEN': 'session-token'})
    return http


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

    async def test_failure_returns_empty(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.return_value = httpx.Response(
            400,
            json={'meta': {'rc': 'error'}},
            request=httpx.Request('POST', 'https://test/api/s/default/cmd/sdn'),
        )

        creds = await signaling.get_turn_credentials()
        assert creds.stun_urls == []
        assert creds.turn_urls == []
        assert creds.turn_username == ''
        assert creds.turn_password == ''

    async def test_exception_returns_empty(self, signaling: LocalSignaling, mock_http: AsyncMock) -> None:
        mock_http.post.side_effect = Exception('connection refused')

        creds = await signaling.get_turn_credentials()
        assert creds.stun_urls == []
        assert creds.turn_urls == []


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


def sdp_offer_event(offer_id: str, sdp: str) -> dict[str, Any]:
    return {'meta': {'rc': 'ok', 'message': 'device:sdp-offer'}, 'data': [{'ssh_sdp_offer': sdp, 'ssh_sdp_offer_id': offer_id}]}


def devmgr_responder(poll_responses: list[httpx.Response], log: list[str]) -> Any:
    """Answer build-ssh-session with ok and get-sdp-offer from poll_responses (last one repeats)."""

    async def post(path: str, json: dict[str, Any]) -> httpx.Response:
        log.append(json['cmd'])
        if json['cmd'] == 'get-sdp-offer':
            return poll_responses.pop(0) if len(poll_responses) > 1 else poll_responses[0]
        return httpx.Response(200, json={'meta': {'rc': 'ok'}, 'data': []}, request=DEVMGR_REQUEST)

    return post


EMPTY_POLL = httpx.Response(200, json={'meta': {'rc': 'ok'}, 'data': []}, request=DEVMGR_REQUEST)


def poll_offer(sdp: str) -> httpx.Response:
    return httpx.Response(200, json={'data': [{'ssh_sdp_offer': sdp}]}, request=DEVMGR_REQUEST)


class TestSdpOfferRace:
    """The offer arrives either as a device:sdp-offer event (Network 11.x) or via get-sdp-offer (older)."""

    async def _build_and_wait(self, signaling: LocalSignaling, turn: TurnCredentials, max_retries: int = 5) -> str:
        await signaling.build_ssh_session(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid', turn=turn)
        return await signaling.poll_sdp_offer(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid', max_retries=max_retries, interval=0.01)

    async def test_event_wins_when_poll_stays_empty(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        """Network 11.0.99: get-sdp-offer returns data=[] forever, the offer only comes over the events websocket."""
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL], fake_ws.log)
        fake_ws.events = [sdp_offer_event('test-uuid', 'v=0\r\nevent-sdp')]

        offer = await self._build_and_wait(signaling, turn_credentials, max_retries=50)

        assert offer == 'v=0\r\nevent-sdp'
        assert len(fake_ws.instances) == 1
        assert fake_ws.instances[0].closed

    async def test_websocket_opened_before_build(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([poll_offer('v=0\r\npoll-sdp')], fake_ws.log)

        await self._build_and_wait(signaling, turn_credentials)

        assert fake_ws.log[:2] == ['ws-connect', 'build-ssh-session']
        ws_kwargs = fake_ws.instances[0].kwargs
        assert ws_kwargs['host'] == '192.168.1.1'
        assert ws_kwargs['port'] == 443
        assert ws_kwargs['site'] == 'default'
        assert ws_kwargs['session_cookie'] == 'session-token'
        assert ws_kwargs['is_unifi_os'] is False

    async def test_poll_wins_on_older_controller(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL, poll_offer('v=0\r\npoll-sdp')], fake_ws.log)

        offer = await self._build_and_wait(signaling, turn_credentials)

        assert offer == 'v=0\r\npoll-sdp'
        assert fake_ws.instances[0].closed

    async def test_event_for_other_uuid_is_ignored(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL, EMPTY_POLL, poll_offer('v=0\r\npoll-sdp')], fake_ws.log)
        fake_ws.events = [
            {'meta': {'rc': 'ok', 'message': 'device:sync'}, 'data': [{'mac': 'aa:bb:cc:dd:ee:ff'}]},
            sdp_offer_event('someone-elses-uuid', 'v=0\r\nwrong-sdp'),
        ]

        offer = await self._build_and_wait(signaling, turn_credentials)

        assert offer == 'v=0\r\npoll-sdp'
        assert fake_ws.instances[0].closed

    async def test_timeout_when_neither_delivers(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL], fake_ws.log)

        with pytest.raises(SDPPollTimeoutError, match='No SDP offer'):
            await self._build_and_wait(signaling, turn_credentials, max_retries=3)

        assert fake_ws.log.count('get-sdp-offer') == 3
        assert fake_ws.instances[0].closed

    async def test_poll_continues_after_event_stream_ends(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL, poll_offer('v=0\r\npoll-sdp')], fake_ws.log)
        fake_ws.end_stream = True

        offer = await self._build_and_wait(signaling, turn_credentials)

        assert offer == 'v=0\r\npoll-sdp'
        assert fake_ws.instances[0].closed

    async def test_websocket_connect_failure_falls_back_to_poll(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.side_effect = devmgr_responder([poll_offer('v=0\r\npoll-sdp')], fake_ws.log)
        fake_ws.connect_error = OSError('connection refused')

        offer = await self._build_and_wait(signaling, turn_credentials)

        assert offer == 'v=0\r\npoll-sdp'

    async def test_build_failure_closes_websocket(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        mock_http.post.return_value = httpx.Response(500, json={'meta': {'rc': 'error'}}, request=DEVMGR_REQUEST)

        with pytest.raises(SignalingError, match='Failed to build SSH'):
            await signaling.build_ssh_session(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid', turn=turn_credentials)

        assert fake_ws.instances[0].closed

    async def test_close_closes_pending_websocket(
        self, signaling: LocalSignaling, mock_http: AsyncMock, turn_credentials: TurnCredentials, fake_ws: type[FakeEventsWebSocket]
    ) -> None:
        """A session torn down between build and poll (e.g. cancelled) still releases the websocket."""
        mock_http.post.side_effect = devmgr_responder([EMPTY_POLL], fake_ws.log)
        await signaling.build_ssh_session(mac='aa:bb:cc:dd:ee:ff', uuid='test-uuid', turn=turn_credentials)

        await signaling.close()

        assert fake_ws.instances[0].closed
