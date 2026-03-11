"""SSH session to a UniFi device over WebRTC.

Orchestrates the full SSH-over-WebRTC flow:
1. Authenticate with the local UniFi controller
2. Request TURN credentials
3. Initiate SSH session on the target device
4. Poll for the device's SDP offer
5. Establish WebRTC peer connection (accept offer, send answer)
6. Wait for the device to open the data channel
7. Provide async read/write interface for terminal I/O
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_mod
from typing import Any

from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import ControllerConfig, SSHConfig
from pyunifiapi.http._local import LocalHttpTransport
from pyunifiapi.signaling._local import LocalSignaling
from pyunifiapi.webrtc._peer import PeerConnection

logger = logging.getLogger(__name__)


class SSHSession:
    """SSH session to a UniFi device over WebRTC data channel.

    Usage::

        async with SSHSession(controller_config, ssh_config) as ssh:
            await ssh.write('ls -la\\n')
            output = await ssh.read(timeout=5.0)
            print(output.decode())

    Or for command execution with prompt detection::

        async with SSHSession(controller_config, ssh_config) as ssh:
            output = await ssh.execute('uptime')
            print(output)
    """

    def __init__(
        self,
        controller: ControllerConfig,
        ssh: SSHConfig,
    ) -> None:
        self._controller_config = controller
        self._ssh_config = ssh

        self._http: LocalHttpTransport | None = None
        self._signaling: LocalSignaling | None = None
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

        # Step 1: Authenticate with local controller
        self._http = LocalHttpTransport(self._controller_config)
        await self._http.login()
        self._signaling = LocalSignaling(self._http, self._controller_config.site)

        # Step 2: Get TURN credentials
        turn = await self._signaling.get_turn_credentials()
        logger.debug('Got TURN credentials: %d STUN, %d TURN URLs', len(turn.stun_urls), len(turn.turn_urls))

        # Step 3: Tell device to build SSH session
        await self._signaling.build_ssh_session(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
            turn=turn,
            username=self._ssh_config.username,
            password=self._ssh_config.password,
        )

        # Step 4: Poll for device's SDP offer
        sdp_offer = await self._signaling.poll_sdp_offer(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
        )

        # Step 5: Create peer connection, accept offer, generate answer
        self._peer = PeerConnection(turn)
        sdp_answer = await self._peer.accept_offer(sdp_offer)

        # Step 6: Send answer back to device via controller
        await self._signaling.send_sdp_answer(
            mac=self._ssh_config.mac,
            uuid=self._uuid,
            sdp_answer=sdp_answer,
        )

        # Step 7: Wait for device to open the data channel
        self._channel = await self._peer.wait_for_channel(timeout=30.0)
        self._connected = True
        logger.info('SSH session established to %s', self._ssh_config.mac)

    async def read(self, timeout: float = 30.0) -> bytes:
        """Read data from the SSH channel.

        Blocks until data is available or timeout is reached.

        Raises:
            SSHSessionError: If the session is not connected.
            asyncio.TimeoutError: If no data within timeout.
        """
        if not self._connected or self._peer is None:
            raise SSHSessionError('SSH session not connected')

        return await asyncio.wait_for(self._peer.message_queue.get(), timeout=timeout)

    async def read_until(self, marker: str | bytes, timeout: float = 30.0) -> bytes:
        """Read data until a marker sequence is found (e.g., shell prompt).

        Args:
            marker: String or bytes to look for in the accumulated output.
            timeout: Maximum time to wait.

        Returns:
            All accumulated data up to and including the marker.

        Raises:
            SSHSessionError: If the session is not connected.
            asyncio.TimeoutError: If marker not found within timeout.
        """
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
        """Write data to the SSH channel.

        Args:
            data: String or bytes to send. Strings are UTF-8 encoded.

        Raises:
            SSHSessionError: If the session is not connected.
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        if not self._connected or self._channel is None:
            raise SSHSessionError('SSH session not connected')

        self._channel.send(data)

    async def execute(self, command: str, timeout: float = 30.0, prompt: str = '# ') -> str:
        """Execute a command and return its output.

        Sends the command followed by a newline, then reads until the prompt
        appears in the output.

        Args:
            command: Shell command to execute.
            timeout: Maximum time to wait for output.
            prompt: Shell prompt string to detect end of output.

        Returns:
            The command output as a string (decoded UTF-8).
        """
        await self.write(command + '\n')
        output = await self.read_until(prompt, timeout=timeout)
        return output.decode('utf-8', errors='replace')

    async def close(self) -> None:
        """Close the SSH session and release all resources."""
        logger.debug('Closing SSH session %s', self._uuid)

        # Close the session on the controller side
        if self._signaling and self._uuid and self._ssh_config:
            try:
                await self._signaling.close_ssh_session(
                    mac=self._ssh_config.mac,
                    uuid=self._uuid,
                )
            except Exception:
                logger.debug('Error closing SSH session on controller', exc_info=True)

        # Close the WebRTC peer connection
        if self._peer:
            await self._peer.close()
            self._peer = None

        # Close the HTTP client
        if self._http:
            await self._http.close()
            self._http = None

        self._channel = None
        self._connected = False
        logger.info('SSH session closed')
