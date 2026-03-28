"""WebSocket-based SDP/ICE signaling for SSH sessions via local UniFi controller.

Replaces the REST polling approach (_local.py) with WebSocket signaling via
/api/ws/webrtc/local. This matches the protocol used by the UniFi controller
web UI since firmware 5.0.x.

Flow:
1. Connect to wss://host/api/ws/webrtc/local
2. Create WebRTC offer with data channel
3. Send offer + ICE servers via WebSocket
4. Send our ICE candidates as they're gathered
5. Receive device's SDP answer via WebSocket
6. Receive device's ICE candidates via WebSocket
7. Send sdpcomplete to signal handshake done
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import uuid as uuid_mod
from typing import Any

import websockets

from pyunifiapi._exceptions import SignalingError
from pyunifiapi._types import TurnCredentials
from pyunifiapi.http._local import LocalHttpTransport

logger = logging.getLogger(__name__)

DEFAULT_ICE_SERVERS = [{'urls': ['stun:stun.cloudflare.com:3478', 'stun:stun.l.google.com:19302', 'stun:global.stun.twilio.com:3478']}]

# Timeout for waiting for the device's SDP answer via WebSocket
WS_ANSWER_TIMEOUT = 300.0


class LocalWebSocketSignaling:
    """WebSocket-based signaling for SSH sessions via local controller.

    Uses wss://host/api/ws/webrtc/local for SDP/ICE exchange instead of
    REST polling. The controller relays messages between us and the device.
    """

    def __init__(self, http: LocalHttpTransport, host: str, port: int = 443, is_unifi_os: bool = False) -> None:
        self._http = http
        self._host = host
        self._port = port
        self._is_unifi_os = is_unifi_os
        self._ws: Any = None
        self._connection_id: str = ''
        self._seq: int = 0

    async def connect(self) -> None:
        """Open the WebSocket connection to the controller's WebRTC relay."""
        url = f'wss://{self._host}:{self._port}/api/ws/webrtc/local'
        cookies = self._http.get_cookies()
        cookie_header = '; '.join(f'{k}={v}' for k, v in cookies.items()) if cookies else ''

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {}
        if cookie_header:
            headers['Cookie'] = cookie_header

        self._ws = await websockets.connect(url, ssl=ssl_context, additional_headers=headers)
        self._connection_id = f'{uuid_mod.uuid4()}-0'
        self._seq = 0
        logger.info('WebSocket connected to %s', url)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def send_offer(self, sdp_offer: str, ice_servers: list[dict] | None = None) -> None:
        """Send our SDP offer to the device via the WebSocket relay."""
        msg = {
            'event': 'offer',
            'seq': self._next_seq(),
            'offer': sdp_offer,
            'connectionId': self._connection_id,
            'iceServers': ice_servers or DEFAULT_ICE_SERVERS,
        }
        await self._ws.send(json.dumps(msg))
        logger.debug('Sent SDP offer (connectionId=%s)', self._connection_id)

    async def send_ice_candidate(self, candidate: str, mid: str = '0', mline_index: int = 0) -> None:
        """Send an ICE candidate to the device."""
        msg = {
            'event': 'icecandidate',
            'seq': self._next_seq(),
            'candidate': candidate,
            'mid': mid,
            'mline_index': mline_index,
        }
        await self._ws.send(json.dumps(msg))

    async def send_sdp_complete(self, sdp_answer: str) -> None:
        """Signal that signaling is complete."""
        msg = {
            'event': 'sdpcomplete',
            'seq': self._next_seq(),
            'answer': sdp_answer,
        }
        await self._ws.send(json.dumps(msg))
        logger.debug('Sent sdpcomplete')

    async def wait_for_answer(self, timeout: float = WS_ANSWER_TIMEOUT) -> tuple[str, list[str]]:
        """Wait for the device's SDP answer and ICE candidates via WebSocket.

        Returns:
            Tuple of (sdp_answer, list of ICE candidate strings).
        """
        sdp_answer: str | None = None
        remote_candidates: list[str] = []

        try:
            async with asyncio.timeout(timeout):
                async for raw_msg in self._ws:
                    if isinstance(raw_msg, bytes):
                        continue

                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue

                    event = msg.get('event')

                    if event == 'answer':
                        sdp_answer = msg.get('answer', '')
                        logger.info('Received SDP answer from device')

                    elif event == 'icecandidate':
                        candidate = msg.get('candidate', '')
                        if candidate:
                            remote_candidates.append(candidate)

                    elif event == 'sdpcomplete':
                        if not sdp_answer:
                            sdp_answer = msg.get('answer', '')
                        logger.info('Received sdpcomplete from device')
                        break

        except TimeoutError:
            if sdp_answer:
                logger.warning('Timed out waiting for sdpcomplete but have answer, proceeding')
            else:
                raise SignalingError(f'No SDP answer from device after {timeout}s')

        if not sdp_answer:
            raise SignalingError('WebSocket closed without receiving SDP answer')

        return sdp_answer, remote_candidates

    async def get_turn_credentials(self) -> TurnCredentials:
        """Return empty TURN credentials (WebSocket signaling uses public STUN servers)."""
        return TurnCredentials(
            stun_urls=['stun:stun.cloudflare.com:3478', 'stun:stun.l.google.com:19302', 'stun:global.stun.twilio.com:3478'],
        )

    async def close_ssh_session(self, mac: str, uuid: str) -> None:
        """Close the WebSocket connection (no REST call needed)."""
        pass

    async def close(self) -> None:
        """Close the WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None
