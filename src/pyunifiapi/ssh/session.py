"""SSH session to a UniFi device over WebRTC.

Orchestrates the full SSH-over-WebRTC flow:
1. Authenticate with the UniFi controller (local or cloud)
2. Request TURN credentials
3. Initiate SSH session on the target device
4. Poll for the device's SDP offer
5. Establish WebRTC peer connection (accept offer, send answer)
6. Wait for the device to open the data channel
7. Provide async read/write interface for terminal I/O

Supports two connection modes:
- **Local**: direct HTTP to controller IP (ControllerConfig)
- **Cloud**: WebRTC via Ubiquiti cloud (CloudConfig)
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_mod
from typing import Any

from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import CloudConfig, ControllerConfig, SSHConfig
from pyunifiapi.webrtc._peer import PeerConnection

logger = logging.getLogger(__name__)


class SSHSession:
    """SSH session to a UniFi device over WebRTC data channel.

    Usage (local)::

        async with SSHSession(controller_config, ssh_config) as ssh:
            output = await ssh.execute('uptime')
            print(output)

    Usage (cloud)::

        async with SSHSession(cloud_config, ssh_config) as ssh:
            output = await ssh.execute('uptime')
            print(output)
    """

    def __init__(
        self,
        controller: ControllerConfig | CloudConfig,
        ssh: SSHConfig,
    ) -> None:
        self._controller_config = controller
        self._ssh_config = ssh
        self._is_cloud = isinstance(controller, CloudConfig)

        self._http: Any = None
        self._cloud_client: Any = None
        self._signaling: Any = None
        self._peer: PeerConnection | None = None
        self._channel: Any = None
        self._uuid: str = ''
        self._connected = False

    async def __aenter__(self) -> SSHSession:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        """Whether the SSH session is currently connected."""
        return self._connected

    async def connect(self) -> None:
        """Execute the full SSH signaling and WebRTC setup flow."""
        self._uuid = str(uuid_mod.uuid4())
        logger.info('Connecting SSH to device %s (session %s)', self._ssh_config.mac, self._uuid)

        if self._is_cloud:
            await self._connect_cloud()
        else:
            await self._connect_local()

    async def _connect_local(self) -> None:
        """Connect via local controller HTTP."""
        from pyunifiapi.http._local import LocalHttpTransport
        from pyunifiapi.signaling._local import LocalSignaling

        assert isinstance(self._controller_config, ControllerConfig)

        self._http = LocalHttpTransport(self._controller_config)
        await self._http.login()
        self._signaling = LocalSignaling(self._http, self._controller_config.site)

        await self._do_ssh_handshake()

    async def _connect_cloud(self) -> None:
        """Connect via cloud WebRTC tunnel."""
        from pyunifiapi.cloud import CloudClient
        from pyunifiapi.signaling._cloud_ssh import CloudSSHSignaling

        assert isinstance(self._controller_config, CloudConfig)

        self._cloud_client = CloudClient(self._controller_config)
        await self._cloud_client.connect()
        self._signaling = CloudSSHSignaling(
            self._cloud_client,
            site=self._controller_config.site,
        )

        await self._do_ssh_handshake()

    async def _do_ssh_handshake(self) -> None:
        """Common SSH handshake flow (works with both local and cloud signaling)."""
        # Step 1: Get TURN credentials
        turn = await self._signaling.get_turn_credentials()
        logger.debug('Got TURN credentials: %d STUN, %d TURN URLs', len(turn.stun_urls), len(turn.turn_urls))

        # Step 2: Tell device to build SSH session
        await self._signaling.build_ssh_session(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
            turn=turn,
            username=self._ssh_config.username,
            password=self._ssh_config.password,
        )

        # Step 3: Poll for device's SDP offer
        sdp_offer = await self._signaling.poll_sdp_offer(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
        )

        # Step 4: Create peer connection, accept offer, generate answer
        self._peer = PeerConnection(turn)
        sdp_answer = await self._peer.accept_offer(sdp_offer)

        # Step 5: Send answer back to device via controller
        await self._signaling.send_sdp_answer(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
            sdp_answer=sdp_answer,
        )

        # Step 6: Wait for device to open the data channel
        self._channel = await self._peer.wait_for_channel(timeout=30.0)
        self._connected = True
        logger.info('SSH session established to %s', self._ssh_config.mac)

    async def read(self, timeout: float = 30.0) -> bytes:
        """Read data from the SSH channel."""
        if not self._connected or self._peer is None:
            raise SSHSessionError('SSH session not connected')

        return await asyncio.wait_for(self._peer.message_queue.get(), timeout=timeout)

    async def read_until(self, marker: str | bytes, timeout: float = 30.0) -> bytes:
        """Read data until a marker sequence is found (e.g., shell prompt)."""
        if isinstance(marker, str):
            marker = marker.encode('utf-8')

        buf = bytearray()
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f'Timed out waiting for marker {marker!r}')

            chunk = await self.read(timeout=remaining)
            buf.extend(chunk)
            if marker in buf:
                return bytes(buf)

    async def write(self, data: str | bytes) -> None:
        """Write data to the SSH channel."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        if not self._connected or self._channel is None:
            raise SSHSessionError('SSH session not connected')

        self._channel.send(data)

    async def execute(self, command: str, timeout: float = 30.0, prompt: str = '# ') -> str:
        """Execute a command and return its output."""
        await self.write(command + '\n')
        output = await self.read_until(prompt, timeout=timeout)
        return output.decode('utf-8', errors='replace')

    async def close(self) -> None:
        """Close the SSH session and release all resources."""
        logger.debug('Closing SSH session %s', self._uuid)

        if self._signaling and self._uuid and self._ssh_config:
            try:
                await self._signaling.close_ssh_session(
                    mac=self._ssh_config.mac,
                    uuid=self._uuid,
                )
            except Exception:
                logger.debug('Error closing SSH session on controller', exc_info=True)

        if self._peer:
            await self._peer.close()
            self._peer = None

        if self._http:
            await self._http.close()
            self._http = None

        if self._cloud_client:
            await self._cloud_client.close()
            self._cloud_client = None

        self._channel = None
        self._connected = False
        logger.info('SSH session closed')
