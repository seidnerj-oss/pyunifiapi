"""UniFi cloud API client - REST API proxied over WebRTC data channel.

Connects to the Ubiquiti cloud, establishes a WebRTC data channel to a
cloud-connected controller, and proxies REST API calls through the
binary-framed data channel protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging

from pyunifiapi._exceptions import WebRTCError
from pyunifiapi._types import CloudConfig
from pyunifiapi.http._cloud import CloudHttpTransport
from pyunifiapi.signaling._cloud import CloudSignaling
from pyunifiapi.webrtc._framing import FrameBuffer, encode_frame
from pyunifiapi.webrtc._peer import PeerConnection

logger = logging.getLogger(__name__)


class CloudClient:
    """UniFi cloud API client.

    Proxies REST API requests to a cloud-connected controller over a
    WebRTC data channel, using the binary framing protocol.

    Usage::

        async with CloudClient(config) as client:
            devices = await client.request('GET', '/api/s/default/stat/device')
    """

    def __init__(self, config: CloudConfig) -> None:
        self._config = config
        self._cloud_http: CloudHttpTransport | None = None
        self._signaling: CloudSignaling | None = None
        self._peer: PeerConnection | None = None
        self._frame_buffer = FrameBuffer()
        self._message_id_counter = 0
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._connected = False

    async def __aenter__(self) -> CloudClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Full cloud connection flow: SSO -> TURN -> WebSocket -> WebRTC."""
        # Step 1: SSO login and get TURN credentials
        self._cloud_http = CloudHttpTransport(self._config)
        await self._cloud_http.sso_login()
        turn = await self._cloud_http.get_turn_credentials(self._config.device_id)

        # Step 2: Connect to cloud WebSocket for signaling
        assert self._cloud_http._client is not None
        cookies = dict(self._cloud_http._client.cookies)
        self._signaling = CloudSignaling(cookies)
        await self._signaling.connect()

        # Step 3: Request SDP offer from cloud device
        offer_response = await self._signaling.request_sdp_offer(self._config.device_id, turn)
        webrtc_id = offer_response.get('webRtcId', '')
        sdp_offer = offer_response.get('sdp', '')

        if not sdp_offer:
            raise WebRTCError('Empty SDP offer from cloud device')

        # Step 4: Create peer connection, accept device's offer, generate answer
        # The device sends the SDP offer, we accept it and create our answer
        self._peer = PeerConnection(turn)
        sdp_answer_str = await self._peer.accept_offer(sdp_offer)

        # Step 5: Send our answer back
        await self._signaling.send_sdp_answer(self._config.device_id, webrtc_id, sdp_answer_str)

        # Step 6: Wait for data channel
        channel = await self._peer.wait_for_channel(timeout=30.0)

        # Set up message handler for framed responses
        @channel.on('message')
        def on_api_message(data: bytes | str) -> None:
            if isinstance(data, str):
                data = data.encode('utf-8')
            frames = self._frame_buffer.feed(data)
            for frame in frames:
                future = self._pending.pop(frame.message_id, None)
                if future and not future.done():
                    content_type = frame.metadata.get('contentType', '')
                    if 'json' in content_type:
                        try:
                            future.set_result(json.loads(frame.payload.decode('utf-8')))
                        except json.JSONDecodeError:
                            future.set_result({'raw': frame.payload.decode('utf-8', errors='replace')})
                    else:
                        future.set_result({'raw': frame.payload})

        self._connected = True
        logger.info('Cloud API connection established to device %s', self._config.device_id)

    async def request(self, method: str, path: str, data: dict | None = None) -> dict:
        """Send a REST API request over the WebRTC data channel.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (e.g., '/api/s/default/stat/device').
            data: Optional JSON body for POST/PUT.

        Returns:
            The parsed JSON response.
        """
        if not self._connected or self._peer is None:
            raise WebRTCError('Cloud client not connected')

        self._message_id_counter += 1
        msg_id = self._message_id_counter

        metadata = {
            'path': path,
            'method': method,
            'contentType': 'application/json',
            'Accept-Encoding': 'gzip',
        }

        payload = b''
        if data:
            payload = json.dumps(data).encode('utf-8')

        frame = encode_frame(msg_id, metadata, payload)

        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        channel = self._peer.data_channel
        if channel is None:
            raise WebRTCError('Data channel not available')
        channel.send(frame)

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError as e:
            self._pending.pop(msg_id, None)
            raise WebRTCError(f'Request timed out: {method} {path}') from e

    async def close(self) -> None:
        """Close the cloud client and release all resources."""
        if self._signaling:
            await self._signaling.close()
            self._signaling = None
        if self._peer:
            await self._peer.close()
            self._peer = None
        if self._cloud_http:
            await self._cloud_http.close()
            self._cloud_http = None
        self._connected = False
