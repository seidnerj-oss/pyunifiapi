"""WebRTC peer connection wrapper for UniFi sessions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from pyunifiapi._constants import ICE_GATHERING_TIMEOUT, WEBRTC_CHANNEL_OPEN_TIMEOUT
from pyunifiapi._exceptions import WebRTCError
from pyunifiapi._types import TurnCredentials

logger = logging.getLogger(__name__)


def _filter_tcp_candidates(sdp: str) -> str:
    """Remove TCP ICE candidates from SDP (UniFi only uses UDP)."""
    lines = sdp.splitlines()
    filtered = [line for line in lines if not (line.startswith('a=candidate:') and ' tcp ' in line.lower())]
    return '\r\n'.join(filtered)


class PeerConnection:
    """Wraps aiortc RTCPeerConnection for UniFi WebRTC sessions.

    Supports two modes:
    - SSH mode: device creates the offer, we answer and wait for data channel
    - Cloud mode: we create the offer with an 'api' data channel, device answers
    """

    def __init__(self, turn_credentials: TurnCredentials) -> None:
        self._turn = turn_credentials
        self._pc: RTCPeerConnection | None = None
        self._data_channel: Any = None
        self._channel_open = asyncio.Event()
        self._message_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def __aenter__(self) -> PeerConnection:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _build_configuration(self) -> RTCConfiguration:
        """Build ICE configuration from TURN credentials."""
        ice_servers = []
        if self._turn.stun_urls:
            ice_servers.append(RTCIceServer(urls=self._turn.stun_urls))
        if self._turn.turn_urls:
            ice_servers.append(
                RTCIceServer(
                    urls=self._turn.turn_urls,
                    username=self._turn.turn_username,
                    credential=self._turn.turn_password,
                )
            )
        return RTCConfiguration(iceServers=ice_servers)

    def _create_pc(self) -> RTCPeerConnection:
        """Create and configure the RTCPeerConnection."""
        config = self._build_configuration()
        pc = RTCPeerConnection(configuration=config)

        @pc.on('datachannel')
        def on_datachannel(channel: object) -> None:
            logger.info('Data channel received: %s', getattr(channel, 'label', 'unknown'))
            self._data_channel = channel
            self._setup_channel_handlers(channel)

        @pc.on('connectionstatechange')
        async def on_state_change() -> None:
            state = pc.connectionState
            logger.debug('Connection state: %s', state)
            if state == 'failed':
                logger.error('WebRTC connection failed')

        return pc

    def _setup_channel_handlers(self, channel: Any) -> None:
        """Set up message and state handlers on a data channel."""

        @channel.on('open')  # type: ignore[union-attr]
        def on_open() -> None:
            logger.debug('Data channel open')
            self._channel_open.set()

        @channel.on('message')  # type: ignore[union-attr]
        def on_message(data: bytes | str) -> None:
            if isinstance(data, str):
                data = data.encode('utf-8')
            self._message_queue.put_nowait(data)

        # If the channel is already open (can happen if device is fast)
        if getattr(channel, 'readyState', None) == 'open':
            self._channel_open.set()

    async def _wait_for_ice_gathering(self, pc: RTCPeerConnection, timeout: float = ICE_GATHERING_TIMEOUT) -> None:
        """Wait for ICE gathering to complete."""
        if pc.iceGatheringState == 'complete':
            return

        gathering_done = asyncio.Event()

        @pc.on('icegatheringstatechange')
        def on_gathering_state() -> None:
            if pc.iceGatheringState == 'complete':
                gathering_done.set()

        try:
            await asyncio.wait_for(gathering_done.wait(), timeout=timeout)
        except TimeoutError:
            logger.warning('ICE gathering timed out after %.1fs (state: %s)', timeout, pc.iceGatheringState)

    async def accept_offer(self, sdp_offer: str) -> str:
        """Accept a remote SDP offer and return the local SDP answer.

        Used in SSH mode where the device creates the offer.
        The device will create the data channel - use wait_for_channel() after
        sending the answer to the device.
        """
        sdp_offer = _filter_tcp_candidates(sdp_offer)

        self._pc = self._create_pc()
        offer = RTCSessionDescription(sdp=sdp_offer, type='offer')
        await self._pc.setRemoteDescription(offer)

        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        # Wait for ICE gathering to complete so the answer includes all candidates
        await self._wait_for_ice_gathering(self._pc)

        local_sdp = self._pc.localDescription
        if local_sdp is None:
            raise WebRTCError('Failed to create local SDP answer')

        logger.debug('Created SDP answer with ICE candidates')
        return local_sdp.sdp

    async def create_offer(self, channel_label: str = 'api') -> str:
        """Create a local SDP offer with a data channel.

        Used in cloud mode where the client initiates.
        """
        self._pc = self._create_pc()
        channel = self._pc.createDataChannel(channel_label, ordered=True)
        self._data_channel = channel
        self._setup_channel_handlers(channel)

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        await self._wait_for_ice_gathering(self._pc)

        local_sdp = self._pc.localDescription
        if local_sdp is None:
            raise WebRTCError('Failed to create local SDP offer')

        return local_sdp.sdp

    async def accept_answer(self, sdp_answer: str) -> None:
        """Set the remote SDP answer (used in cloud mode after create_offer)."""
        if self._pc is None:
            raise WebRTCError('No peer connection - call create_offer first')

        sdp_answer = _filter_tcp_candidates(sdp_answer)
        answer = RTCSessionDescription(sdp=sdp_answer, type='answer')
        await self._pc.setRemoteDescription(answer)

    async def wait_for_channel(self, timeout: float = WEBRTC_CHANNEL_OPEN_TIMEOUT) -> Any:
        """Wait for the data channel to open.

        In SSH mode, the device creates the channel after receiving our SDP answer.
        In cloud mode, our channel opens after the device processes our offer.
        """
        try:
            await asyncio.wait_for(self._channel_open.wait(), timeout=timeout)
        except TimeoutError as e:
            raise WebRTCError(f'Data channel did not open within {timeout}s') from e

        if self._data_channel is None:
            raise WebRTCError('Channel open event fired but no channel available')

        return self._data_channel

    @property
    def data_channel(self) -> Any:
        """The active data channel, if any."""
        return self._data_channel

    @property
    def message_queue(self) -> asyncio.Queue[bytes]:
        """Queue of incoming messages from the data channel."""
        return self._message_queue

    async def close(self) -> None:
        """Close the peer connection and all channels."""
        if self._pc:
            await self._pc.close()
            self._pc = None
        self._data_channel = None
        self._channel_open.clear()
