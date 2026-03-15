"""UniFi cloud API client - REST API proxied over WebRTC data channel.

Connects to the Ubiquiti cloud via MQTT signaling, establishes a WebRTC
data channel to a cloud-connected controller, and proxies REST API calls
through the binary-framed data channel protocol.

Connection flow:
1. SSO login -> AWS credentials + TURN credentials
2. MQTT signaling (AWS IoT) -> SDP offer/answer exchange
3. WebRTC peer connection -> data channel
4. REST API calls proxied over the data channel
"""

from __future__ import annotations

import asyncio
import json
import logging

from pyunifiapi._exceptions import WebRTCError
from pyunifiapi._types import CloudConfig
from pyunifiapi.http._cloud import CloudHttpTransport
from pyunifiapi.signaling._mqtt import MqttSignaling
from pyunifiapi.webrtc._framing import BinmeStreamParser, encode_frame
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
        self._signaling: MqttSignaling | None = None
        self._peer: PeerConnection | None = None
        self._message_id_counter = 0
        self._pending: dict[str, asyncio.Future[dict]] = {}
        self._connected = False

    async def __aenter__(self) -> CloudClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Full cloud connection flow: SSO -> MQTT signaling -> WebRTC."""
        self._cloud_http = CloudHttpTransport(self._config)
        await self._cloud_http.sso_login()
        turn = await self._cloud_http.get_turn_credentials(self._config.device_id)

        assert self._cloud_http._aws_credentials is not None
        self._signaling = MqttSignaling(
            aws_credentials=self._cloud_http._aws_credentials,
            identity_id=self._cloud_http._aws_credentials.get('identity_id', ''),
        )
        await self._signaling.connect()

        self._peer = PeerConnection(turn)
        offer_sdp, local_candidates = await self._peer.create_offer('placeholder')

        answer = await self._signaling.exchange_sdp(
            host_id=self._config.device_id,
            offer_sdp=offer_sdp,
            local_candidates=local_candidates,
            turn=turn,
        )

        remote_sdp = answer.get('answer', answer.get('sdp', ''))
        if not remote_sdp:
            raise WebRTCError(f'Empty SDP answer from cloud device. Response: {answer}')

        remote_candidates = [ice.get('candidate', '') for ice in answer.get('ice_candidates', []) if ice.get('candidate')]
        await self._peer.accept_answer(remote_sdp, remote_candidates)
        await self._peer.wait_for_channel(timeout=30.0)

        api_channel = self._peer.create_data_channel('api:1')
        self._peer.data_channel = api_channel

        api_open = asyncio.Event()
        loop = asyncio.get_event_loop()

        def on_api_open() -> None:
            loop.call_soon_threadsafe(api_open.set)

        stream_parser = BinmeStreamParser()

        def on_api_message(data: bytes | str) -> None:
            if isinstance(data, str):
                data = data.encode('utf-8')
            for frame in stream_parser.feed(data):
                request_id = frame.request_id
                future = self._pending.pop(request_id, None)
                if future and not future.done():
                    loop.call_soon_threadsafe(self._resolve_response, future, frame.body)

        api_channel.on_open(on_api_open)
        api_channel.on_message(on_api_message)

        if api_channel.is_open():
            api_open.set()
        else:
            await asyncio.wait_for(api_open.wait(), timeout=10.0)

        self._connected = True
        logger.info('Cloud API connection established to device %s', self._config.device_id)

    @staticmethod
    def _resolve_response(future: asyncio.Future, body: bytes) -> None:
        """Parse response body and resolve the future."""
        if future.done():
            return
        if body:
            try:
                future.set_result(json.loads(body.decode('utf-8')))
            except (json.JSONDecodeError, UnicodeDecodeError):
                future.set_result({'raw': body})
        else:
            future.set_result({})

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

        metadata: dict = {
            'path': path,
            'method': method,
            'headers': {'content-length': 0},
        }

        payload = b''
        if data:
            payload = json.dumps(data).encode('utf-8')
            metadata['headers'] = {
                'content-type': 'application/json',
                'content-length': len(payload),
            }

        frame_bytes, request_id = encode_frame(0, metadata, payload)

        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        channel = self._peer.data_channel
        if channel is None:
            raise WebRTCError('Data channel not available')
        channel.send(frame_bytes)

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError as e:
            self._pending.pop(request_id, None)
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
