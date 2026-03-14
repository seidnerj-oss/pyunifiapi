"""SDP/ICE signaling for cloud API via WebSocket.

Uses the Ubiquiti cloud WebSocket at wss://cloudaccess.svc.ui.com
for SDP exchange when establishing WebRTC connections through the cloud.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid as uuid_mod
from typing import Any

import websockets

from pyunifiapi._constants import CLOUD_WSS_URL
from pyunifiapi._exceptions import SignalingError
from pyunifiapi._types import TurnCredentials

logger = logging.getLogger(__name__)


class CloudSignaling:
    """SDP/ICE signaling for cloud API via WebSocket.

    Connects to the Ubiquiti cloud WebSocket and exchanges SDP offers/answers
    for establishing WebRTC data channels to cloud-connected controllers.
    """

    def __init__(self, cookies: dict[str, str]) -> None:
        self._cookies = cookies
        self._ws: Any = None
        self._pending_responses: dict[str, asyncio.Future[dict]] = {}
        self._listener_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None

    async def __aenter__(self) -> CloudSignaling:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Connect to the cloud WebSocket."""
        cookie_header = '; '.join(f'{k}={v}' for k, v in self._cookies.items())
        self._ws = await websockets.connect(
            CLOUD_WSS_URL,
            extra_headers={
                'Cookie': cookie_header,
                'Origin': 'https://unifi.ubnt.com',
            },
        )
        self._listener_task = asyncio.create_task(self._listener_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info('Connected to cloud WebSocket')

    async def _listener_loop(self) -> None:
        """Listen for WebSocket messages and dispatch responses."""
        assert self._ws is not None
        try:
            async for raw_message in self._ws:
                try:
                    msg = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning('Non-JSON WebSocket message: %s', raw_message[:100])
                    continue

                if msg.get('message') == 'action:response':
                    action_id = msg.get('action_id', '')
                    if action_id in self._pending_responses:
                        self._pending_responses[action_id].set_result(msg.get('response', {}))
        except websockets.ConnectionClosed:
            logger.info('Cloud WebSocket closed')
        except Exception:
            logger.exception('Error in cloud WebSocket listener')

    async def _ping_loop(self) -> None:
        """Send periodic pings to keep the WebSocket alive."""
        assert self._ws is not None
        try:
            while True:
                await asyncio.sleep(10)
                await self._ws.ping()
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    async def request_sdp_offer(self, device_id: str, turn: TurnCredentials) -> dict:
        """Request an SDP offer from a cloud-connected device.

        Sends an sdp_exchange action request via WebSocket and waits for the response.

        Returns:
            Dict with 'webRtcId' and 'sdp' keys.
        """
        assert self._ws is not None
        action_id = str(uuid_mod.uuid4())
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending_responses[action_id] = future

        msg = {
            'message': 'action:request',
            'action': 'sdp_exchange',
            'action_id': action_id,
            'args': {
                'device_id': device_id,
                'payload': {
                    'username': turn.turn_username,
                    'password': turn.turn_password,
                    'ttl': 86400,
                    'type': 'OFFER',
                    'stunUri': turn.stun_urls[0] if turn.stun_urls else '',
                    'turnUri': turn.turn_urls[0] if turn.turn_urls else '',
                },
            },
        }

        await self._ws.send(json.dumps(msg))
        logger.debug('Sent SDP offer request for device %s', device_id)

        try:
            response = await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError as e:
            raise SignalingError(f'Timed out waiting for SDP offer from cloud device {device_id}') from e
        finally:
            self._pending_responses.pop(action_id, None)

        return response

    async def send_sdp_answer(self, device_id: str, webrtc_id: str, sdp_answer: str) -> None:
        """Send our SDP answer back to the cloud device."""
        assert self._ws is not None
        action_id = str(uuid_mod.uuid4())

        msg = {
            'message': 'action:request',
            'action': 'sdp_exchange',
            'action_id': action_id,
            'args': {
                'device_id': device_id,
                'payload': {
                    'sdpAnswer': sdp_answer,
                    'type': 'ANSWER',
                    'webRtcId': webrtc_id,
                },
            },
        }

        await self._ws.send(json.dumps(msg))
        logger.debug('Sent SDP answer for device %s', device_id)

    async def close(self) -> None:
        """Close the WebSocket and stop background tasks."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
