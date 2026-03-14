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
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._connected = False

    async def __aenter__(self) -> CloudClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Full cloud connection flow: SSO -> MQTT signaling -> WebRTC.

        Uses legacy signaling (HTTP POST + MQTT) for NetServer controllers
        (UCG Ultra, UDM, UDR, etc.), which covers all UniFi OS controllers.
        """
        # Step 1: SSO login and get AWS credentials + TURN credentials
        self._cloud_http = CloudHttpTransport(self._config)
        await self._cloud_http.sso_login()
        turn = await self._cloud_http.get_turn_credentials(self._config.device_id)

        # Step 2: Connect to MQTT signaling (AWS IoT)
        assert self._cloud_http._aws_credentials is not None
        self._signaling = MqttSignaling(
            aws_credentials=self._cloud_http._aws_credentials,
            identity_id=self._cloud_http._aws_credentials.get('identity_id', ''),
        )
        await self._signaling.connect()

        # Step 3: Create WebRTC peer connection with placeholder channel
        # The placeholder triggers SDP negotiation; actual API channels are created after
        self._peer = PeerConnection(turn)
        self._peer._pc = self._peer._create_pc()
        placeholder = self._peer._pc.createDataChannel('placeholder', ordered=True)
        self._peer._data_channel = placeholder
        self._peer._setup_channel_handlers(placeholder)

        # Step 4: Exchange SDP via cloud signaling (trickle ICE over MQTT)
        answer = await self._signaling.exchange_sdp(
            host_id=self._config.device_id,
            pc=self._peer._pc,
            turn=turn,
        )

        remote_sdp = answer.get('answer', answer.get('sdp', ''))
        if not remote_sdp:
            raise WebRTCError(f'Empty SDP answer from cloud device. Response: {answer}')

        # Step 5: Set remote description, add remote ICE candidates, wait for channel
        from aiortc import RTCSessionDescription
        await self._peer._pc.setRemoteDescription(
            RTCSessionDescription(sdp=remote_sdp, type='answer')
        )

        # Add remote ICE candidates (trickle ICE)
        from aioice.candidate import Candidate as AioIceCandidate
        from aiortc.rtcicetransport import candidate_from_aioice

        for ice in answer.get('ice_candidates', []):
            candidate_str = ice.get('candidate', '')
            if candidate_str:
                candidate_str = candidate_str.replace('a=', '', 1)
                try:
                    aioice_candidate = AioIceCandidate.from_sdp(candidate_str)
                    rtc_candidate = candidate_from_aioice(aioice_candidate)
                    rtc_candidate.sdpMid = '0'
                    rtc_candidate.sdpMLineIndex = 0
                    await self._peer._pc.addIceCandidate(rtc_candidate)
                    logger.debug('Added remote ICE candidate: %s:%d (%s)', rtc_candidate.ip, rtc_candidate.port, rtc_candidate.type)
                except Exception as e:
                    logger.debug('Failed to add remote ICE candidate: %s', e)

        await self._peer.wait_for_channel(timeout=30.0)

        # Create the actual API data channel after placeholder is open
        api_channel = self._peer._pc.createDataChannel('api:1', ordered=True)
        self._peer._data_channel = api_channel

        api_open = asyncio.Event()

        @api_channel.on('open')
        def on_api_open() -> None:
            api_open.set()

        if getattr(api_channel, 'readyState', None) == 'open':
            api_open.set()
        else:
            await asyncio.wait_for(api_open.wait(), timeout=10.0)

        channel = api_channel

        # Streaming binme parser handles chunked responses across DC messages
        stream_parser = BinmeStreamParser()

        @channel.on('message')
        def on_api_message(data: bytes | str) -> None:
            if isinstance(data, str):
                data = data.encode('utf-8')
            for frame in stream_parser.feed(data):
                request_id = frame.request_id
                future = self._pending.pop(request_id, None)
                if future and not future.done():
                    self._resolve_response(future, frame.body)

        self._connected = True
        logger.info('Cloud API connection established to device %s', self._config.device_id)

    @staticmethod
    def _resolve_response(future: asyncio.Future, body: bytes) -> None:
        """Parse response body and resolve the future."""
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
