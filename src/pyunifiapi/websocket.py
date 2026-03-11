"""WebSocket client for real-time UniFi controller events."""

from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from pyunifiapi.models.message import Message

logger = logging.getLogger(__name__)

# WebSocket path patterns
WS_PATH_CLASSIC = '/wss/s/{site}/events'
WS_PATH_UNIFI_OS = '/proxy/network/wss/s/{site}/events'


class WebSocketClient:
    """WebSocket client for receiving real-time events from a UniFi controller.

    Connects to the controller's event WebSocket and yields parsed Message
    objects as they arrive.
    """

    def __init__(
        self,
        host: str,
        port: int,
        site: str,
        session_cookie: str,
        is_unifi_os: bool,
        ssl_verify: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._site = site
        self._session_cookie = session_cookie
        self._is_unifi_os = is_unifi_os
        self._ssl_verify = ssl_verify
        self._connection: ClientConnection | None = None

    @property
    def url(self) -> str:
        path_template = WS_PATH_UNIFI_OS if self._is_unifi_os else WS_PATH_CLASSIC
        path = path_template.format(site=self._site)
        return f'wss://{self._host}:{self._port}{path}'

    async def connect(self) -> None:
        """Open the WebSocket connection."""
        ssl_context = ssl.create_default_context()
        if not self._ssl_verify:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        headers = {'Cookie': f'TOKEN={self._session_cookie}'}
        self._connection = await websockets.connect(
            self.url,
            ssl=ssl_context,
            additional_headers=headers,
        )
        logger.info('WebSocket connected to %s', self.url)

    async def listen(self) -> AsyncIterator[Message]:
        """Yield parsed Message objects from the WebSocket stream.

        The caller should iterate this in a loop. The iterator ends
        when the connection is closed.
        """
        if self._connection is None:
            raise RuntimeError('WebSocket not connected')

        async for raw_msg in self._connection:
            if isinstance(raw_msg, bytes):
                raw_msg = raw_msg.decode('utf-8', errors='replace')
            try:
                import json

                data = json.loads(raw_msg)
            except (ValueError, TypeError):
                logger.debug('Ignoring non-JSON WebSocket message')
                continue

            if isinstance(data, dict):
                yield Message.from_raw(data)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield Message.from_raw(item)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info('WebSocket closed')
