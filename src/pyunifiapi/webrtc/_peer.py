"""WebRTC peer connection wrapper for UniFi sessions.

Uses libdatachannel-py for native DTLS/ICE. Callbacks from libdatachannel
fire on a C++ thread; this module bridges them to asyncio using
loop.call_soon_threadsafe().
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import libdatachannel as ldc

from pyunifiapi._constants import ICE_GATHERING_TIMEOUT, SDP_DESCRIPTION_TIMEOUT, WEBRTC_CHANNEL_OPEN_TIMEOUT
from pyunifiapi._exceptions import WebRTCError
from pyunifiapi._types import TurnCredentials

logger = logging.getLogger(__name__)


def _filter_tcp_candidates(sdp: str) -> str:
    """Remove TCP ICE candidates from SDP (UniFi only uses UDP)."""
    lines = sdp.splitlines()
    filtered = [line for line in lines if not (line.startswith('a=candidate:') and ' tcp ' in line.lower())]
    return '\r\n'.join(filtered)


async def _await_threading_event(event: threading.Event, timeout: float) -> bool:
    """Wait for a threading.Event without blocking the asyncio event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, event.wait, timeout)


class PeerConnection:
    """Wraps libdatachannel PeerConnection for UniFi WebRTC sessions.

    Supports two modes:
    - SSH mode: device creates the offer, we answer and wait for data channel
    - Cloud mode: we create the offer with a data channel, device answers
    """

    def __init__(self, turn_credentials: TurnCredentials) -> None:
        self._turn = turn_credentials
        self._pc: ldc.PeerConnection | None = None
        self._data_channel: ldc.DataChannel | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._channel_open = asyncio.Event()
        self._message_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._local_candidates: list[ldc.Candidate] = []
        self._local_description_sdp: str | None = None
        self._desc_ready = threading.Event()
        self._gathering_done = threading.Event()

    async def __aenter__(self) -> PeerConnection:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _build_configuration(self) -> ldc.Configuration:
        """Build ICE configuration from TURN credentials."""
        config = ldc.Configuration()
        ice_servers = []
        for url in self._turn.stun_urls:
            ice_servers.append(ldc.IceServer(url))
        for url in self._turn.turn_urls:
            server = ldc.IceServer(url)
            server.username = self._turn.turn_username
            server.password = self._turn.turn_password
            ice_servers.append(server)
        if ice_servers:
            config.ice_servers = ice_servers
        return config

    def _create_pc(self) -> ldc.PeerConnection:
        """Create and configure the PeerConnection with callbacks."""
        self._loop = asyncio.get_event_loop()
        config = self._build_configuration()
        pc = ldc.PeerConnection(config)

        def on_state(state: ldc.PeerConnection.State) -> None:
            logger.debug('Connection state: %s', state)
            if state == ldc.PeerConnection.State.Failed:
                logger.error('WebRTC connection failed')

        def on_gathering(state: ldc.PeerConnection.GatheringState) -> None:
            logger.debug('ICE gathering state: %s', state)
            if state == ldc.PeerConnection.GatheringState.Complete:
                self._gathering_done.set()

        def on_local_desc(desc: ldc.Description) -> None:
            self._local_description_sdp = str(desc)
            logger.debug('Local description generated (type: %s)', desc.type_string())
            self._desc_ready.set()

        def on_local_candidate(candidate: ldc.Candidate) -> None:
            self._local_candidates.append(candidate)

        def on_data_channel(dc: ldc.DataChannel) -> None:
            logger.info('Data channel received: %s', dc.label())
            self._data_channel = dc
            self._setup_channel_handlers(dc)

        pc.on_state_change(on_state)
        pc.on_gathering_state_change(on_gathering)
        pc.on_local_description(on_local_desc)
        pc.on_local_candidate(on_local_candidate)
        pc.on_data_channel(on_data_channel)

        return pc

    def _setup_channel_handlers(self, channel: ldc.DataChannel) -> None:
        """Set up message and state handlers on a data channel."""
        loop = self._loop

        def on_open() -> None:
            logger.info('Data channel open: label=%s, id=%s', channel.label(), channel.id())
            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._channel_open.set)
            else:
                self._channel_open.set()

        def on_closed() -> None:
            logger.info('Data channel closed: label=%s', channel.label())

        def on_error(error: str) -> None:
            logger.error('Data channel error: label=%s, error=%s', channel.label(), error)

        def on_message(data: bytes | str) -> None:
            if isinstance(data, str):
                logger.debug('Data channel recv (str, %d chars): %s', len(data), repr(data[:200]))
                data = data.encode('utf-8')
            else:
                logger.debug('Data channel recv (bytes, %d bytes): %s', len(data), repr(data[:200]))
            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._message_queue.put_nowait, data)
            else:
                self._message_queue.put_nowait(data)

        channel.on_open(on_open)
        channel.on_closed(on_closed)
        channel.on_error(on_error)
        channel.on_message(on_message)

        if channel.is_open():
            logger.info('Data channel already open: label=%s', channel.label())
            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._channel_open.set)
            else:
                self._channel_open.set()

    async def accept_offer(self, sdp_offer: str) -> str:
        """Accept a remote SDP offer and return the local SDP answer.

        Used in SSH mode where the device creates the offer.
        The device will create the data channel - use wait_for_channel() after
        sending the answer to the device.
        """
        sdp_offer = _filter_tcp_candidates(sdp_offer)

        self._desc_ready.clear()
        self._gathering_done.clear()
        self._local_candidates.clear()

        self._pc = self._create_pc()
        self._pc.set_remote_description(ldc.Description(sdp_offer, 'offer'))

        if not await _await_threading_event(self._desc_ready, SDP_DESCRIPTION_TIMEOUT):
            raise WebRTCError('Timed out waiting for local SDP answer generation')

        if not await _await_threading_event(self._gathering_done, ICE_GATHERING_TIMEOUT):
            logger.warning('ICE gathering timed out after %.1fs', ICE_GATHERING_TIMEOUT)

        if self._local_description_sdp is None:
            raise WebRTCError('Failed to create local SDP answer')

        logger.debug('Created SDP answer with %d ICE candidates', len(self._local_candidates))
        return self._local_description_sdp

    async def create_offer(self, channel_label: str = 'placeholder') -> tuple[str, list[str]]:
        """Create a local SDP offer with a data channel.

        Used in cloud mode where the client initiates.

        Returns:
            Tuple of (offer_sdp, list of ICE candidate strings).
        """
        self._desc_ready.clear()
        self._gathering_done.clear()
        self._local_candidates.clear()

        self._pc = self._create_pc()
        channel = self._pc.create_data_channel(channel_label)
        self._data_channel = channel
        self._setup_channel_handlers(channel)

        if not await _await_threading_event(self._desc_ready, SDP_DESCRIPTION_TIMEOUT):
            raise WebRTCError('Timed out waiting for local SDP offer generation')

        if not await _await_threading_event(self._gathering_done, ICE_GATHERING_TIMEOUT):
            logger.warning('ICE gathering timed out after %.1fs', ICE_GATHERING_TIMEOUT)

        if self._local_description_sdp is None:
            raise WebRTCError('Failed to create local SDP offer')

        candidates = [c.candidate() for c in self._local_candidates]
        return self._local_description_sdp, candidates

    async def accept_answer(self, sdp_answer: str, remote_candidates: list[str] | None = None) -> None:
        """Set the remote SDP answer and add remote ICE candidates."""
        if self._pc is None:
            raise WebRTCError('No peer connection - call create_offer first')

        sdp_answer = _filter_tcp_candidates(sdp_answer)
        self._pc.set_remote_description(ldc.Description(sdp_answer, 'answer'))

        for candidate_str in remote_candidates or []:
            if candidate_str:
                try:
                    self._pc.add_remote_candidate(ldc.Candidate(candidate_str, 'data'))
                    logger.debug('Added remote ICE candidate')
                except Exception as e:
                    logger.debug('Failed to add remote ICE candidate: %s', e)

    def create_data_channel(self, label: str) -> ldc.DataChannel:
        """Create an additional data channel on the existing connection."""
        if self._pc is None:
            raise WebRTCError('No peer connection')
        channel = self._pc.create_data_channel(label)
        return channel

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
    def pc(self) -> ldc.PeerConnection | None:
        """The underlying libdatachannel PeerConnection."""
        return self._pc

    @property
    def data_channel(self) -> Any:
        """The active data channel, if any."""
        return self._data_channel

    @data_channel.setter
    def data_channel(self, channel: ldc.DataChannel | None) -> None:
        self._data_channel = channel

    @property
    def message_queue(self) -> asyncio.Queue[bytes]:
        """Queue of incoming messages from the data channel."""
        return self._message_queue

    async def close(self) -> None:
        """Close the peer connection and all channels."""
        if self._pc:
            self._pc.close()
            self._pc = None
        self._data_channel = None
        self._channel_open.clear()
