"""High-level UniFi cloud controller with typed handlers.

Wraps :class:`CloudClient` (WebRTC data channel) with the same handler-based
interface as the local :class:`Controller`, so callers can use either
interchangeably.
"""

from __future__ import annotations

import asyncio
import logging

from pyunifiapi._types import CloudConfig
from pyunifiapi.cloud import CloudClient
from pyunifiapi.handlers.device import DeviceHandler
from pyunifiapi.handlers.site import SiteHandler

logger = logging.getLogger(__name__)


class CloudController:
    """Cloud-connected UniFi controller with typed handlers.

    Provides the same public interface as :class:`Controller` -
    ``.devices``, ``.sites``, ``.execute()`` - but proxies all REST API
    calls over a WebRTC data channel via :class:`CloudClient`.

    Usage::

        config = CloudConfig(
            username='sso@email.com',
            password='pass',
            device_id='abc123',
            totp_secret='JBSWY3DPEHPK3PXP',
            site='default',
        )
        controller = CloudController(config)
        await controller.connect()
        await controller.initialize()

        for mac, device in controller.devices.items():
            print(device.name, device.ip)

        await controller.disconnect()
    """

    def __init__(self, config: CloudConfig) -> None:
        self.config = config
        self._cloud_client: CloudClient | None = None

        # Handlers (same as Controller)
        self.devices = DeviceHandler()
        self.sites = SiteHandler()

    async def connect(self) -> None:
        """Establish the WebRTC data channel to the cloud-connected controller."""
        self._cloud_client = CloudClient(self.config)
        await self._cloud_client.connect()
        logger.info('Cloud controller connected (device_id=%s)', self.config.device_id)

    async def initialize(self) -> None:
        """Fetch initial data (devices, sites) from the controller via cloud."""
        site = self.config.site

        async def fetch(path: str) -> list[dict]:
            # Cloud-connected controllers are always UniFi OS
            full_path = f'/proxy/network{path}'.format(site=site)
            resp = await self.request('GET', full_path)
            if isinstance(resp, dict):
                result: list[dict] = resp.get('data', [])
                return result
            return []

        results = await asyncio.gather(
            fetch('/api/s/{site}/stat/device'),
            fetch('/api/self/sites'),
            return_exceptions=True,
        )

        if isinstance(results[0], BaseException):
            logger.warning('Failed to fetch devices: %s', results[0])
        else:
            self.devices.process_full(results[0])
            logger.debug('Loaded %d devices', len(results[0]))

        if isinstance(results[1], BaseException):
            logger.warning('Failed to fetch sites: %s', results[1])
        else:
            self.sites.process_full(results[1])
            logger.debug('Loaded %d sites', len(results[1]))

    async def request(self, method: str, path: str, data: dict | None = None) -> dict:
        """Send a REST API request over the WebRTC data channel."""
        assert self._cloud_client is not None
        return await self._cloud_client.request(method, path, data)

    async def execute(self, request_obj: object) -> list[dict]:
        """Execute an ApiRequest and return the data array.

        Accepts any object with ``method``, ``data``, and
        ``full_path(site, is_unifi_os)`` attributes (same as Controller).
        Cloud-connected controllers are always UniFi OS.
        """
        method = getattr(request_obj, 'method', 'GET')
        data = getattr(request_obj, 'data', None)
        full_path_fn = getattr(request_obj, 'full_path', None)
        if full_path_fn is None:
            raise TypeError(f'{type(request_obj).__name__} has no full_path method')

        # Cloud controllers are always UniFi OS
        path = full_path_fn(self.config.site, True)
        resp = await self.request(method, path, data)
        if isinstance(resp, dict):
            result: list[dict] = resp.get('data', [])
            return result
        return []

    async def disconnect(self) -> None:
        """Close the cloud connection and release resources."""
        if self._cloud_client:
            await self._cloud_client.close()
            self._cloud_client = None

    async def __aenter__(self) -> CloudController:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()
