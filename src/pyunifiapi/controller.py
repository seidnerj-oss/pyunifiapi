"""High-level UniFi controller with typed handlers and real-time WebSocket events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from pyunifiapi._types import ControllerConfig
from pyunifiapi.handlers.client import ClientHandler
from pyunifiapi.handlers.device import DeviceHandler
from pyunifiapi.handlers.dpi import DPIRestrictionAppHandler, DPIRestrictionGroupHandler
from pyunifiapi.handlers.event import EventHandler
from pyunifiapi.handlers.firewall import FirewallPolicyHandler, FirewallZoneHandler
from pyunifiapi.handlers.port_forward import PortForwardHandler
from pyunifiapi.handlers.site import SiteHandler
from pyunifiapi.handlers.system_information import SystemInformationHandler
from pyunifiapi.handlers.traffic_route import TrafficRouteHandler
from pyunifiapi.handlers.traffic_rule import TrafficRuleHandler
from pyunifiapi.handlers.voucher import VoucherHandler
from pyunifiapi.handlers.wlan import WlanHandler
from pyunifiapi.http._local import LocalHttpTransport
from pyunifiapi.models.message import MessageKey
from pyunifiapi.websocket import WebSocketClient

logger = logging.getLogger(__name__)

SessionStateCallback = Callable[['SessionState'], None]


class SessionState:
    """Current state of the controller session."""

    def __init__(self, is_unifi_os: bool = False, version: str = '') -> None:
        self.is_unifi_os = is_unifi_os
        self.version = version


class Controller:
    """High-level UniFi controller client with typed handlers and WebSocket support.

    Provides:
    - Typed handler collections (devices, clients, wlans, etc.)
    - Automatic initial data fetch
    - Real-time WebSocket event processing
    - API action methods that execute requests

    Usage::

        controller = Controller(config)
        await controller.connect()
        await controller.initialize()

        for mac, device in controller.devices.items():
            print(device.name, device.ip)

        # Start WebSocket listener (runs until stopped)
        ws_task = asyncio.create_task(controller.start())

        # ... later ...
        await controller.disconnect()
    """

    def __init__(self, config: ControllerConfig) -> None:
        self._config = config
        self._http: LocalHttpTransport | None = None
        self._ws: WebSocketClient | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._session = SessionState()

        # Handlers
        self.devices = DeviceHandler()
        self.clients = ClientHandler()
        self.events = EventHandler()
        self.wlans = WlanHandler()
        self.sites = SiteHandler()
        self.vouchers = VoucherHandler()
        self.port_forwards = PortForwardHandler()
        self.traffic_rules = TrafficRuleHandler()
        self.traffic_routes = TrafficRouteHandler()
        self.firewall_zones = FirewallZoneHandler()
        self.firewall_policies = FirewallPolicyHandler()
        self.dpi_apps = DPIRestrictionAppHandler()
        self.dpi_groups = DPIRestrictionGroupHandler()
        self.system_information = SystemInformationHandler()

        # WebSocket message key -> handler mapping
        self._ws_handlers: dict[str, Callable[[list[dict]], None]] = {
            MessageKey.DEVICE: self.devices.process_raw,
            MessageKey.CLIENT: self.clients.process_raw,
            MessageKey.CLIENT_REMOVED: self.clients.process_raw,
            MessageKey.EVENT: self.events.process_raw,
            MessageKey.WLAN_CONF_UPDATED: self.wlans.process_raw,
            MessageKey.PORT_FORWARD_UPDATED: self.port_forwards.process_raw,
            MessageKey.DPI_APP_UPDATED: self.dpi_apps.process_raw,
            MessageKey.DPI_GROUP_UPDATED: self.dpi_groups.process_raw,
        }

    # --- Connection lifecycle ---

    async def connect(self) -> None:
        """Login to the controller and detect UniFi OS."""
        self._http = LocalHttpTransport(self._config)
        await self._http.login()
        self._session.is_unifi_os = await self._detect_unifi_os()
        logger.info('Connected to controller (UniFi OS: %s)', self._session.is_unifi_os)

    async def _detect_unifi_os(self) -> bool:
        """Detect whether the controller runs UniFi OS (Dream Machine, UCG, UDR, etc.).

        Checks multiple indicators:
        1. GET / returns JSON with 'meta' field (classic detection)
        2. GET /api/system returns JSON (UniFi OS system endpoint)
        """
        assert self._http is not None
        try:
            resp = await self._http.get('/')
            content_type = resp.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and 'meta' in data:
                        return True
                except (ValueError, TypeError):
                    pass

            # Fallback: check if /api/system exists (UniFi OS only)
            resp = await self._http.get('/api/system')
            content_type = resp.headers.get('content-type', '')
            if 'application/json' in content_type and resp.status_code == 200:
                return True
        except Exception:
            logger.debug('UniFi OS detection failed, assuming classic controller')
        return False

    async def initialize(self) -> None:
        """Fetch initial data for all handlers from the REST API."""
        assert self._http is not None
        is_os = self._session.is_unifi_os
        site = self._config.site

        async def fetch(path: str) -> list[dict]:
            assert self._http is not None
            full_path = f'/proxy/network{path}' if is_os else path
            full_path = full_path.format(site=site)
            resp = await self._http.get(full_path)
            result: list[dict] = resp.json().get('data', [])
            return result

        # Fetch all collections in parallel
        results = await asyncio.gather(
            fetch('/api/s/{site}/stat/device'),
            fetch('/api/s/{site}/stat/sta'),
            fetch('/api/s/{site}/list/wlanconf'),
            fetch('/api/s/{site}/stat/sysinfo'),
            fetch('/api/s/{site}/list/portforward'),
            fetch('/api/s/{site}/stat/event?_limit=3000'),
            return_exceptions=True,
        )

        handlers_data: list[tuple[str, Callable[[list[dict]], None], list[dict] | BaseException]] = [
            ('devices', self.devices.process_full, results[0]),
            ('clients', self.clients.process_full, results[1]),
            ('wlans', self.wlans.process_full, results[2]),
            ('system_information', self.system_information.process_full, results[3]),
            ('port_forwards', self.port_forwards.process_full, results[4]),
            ('events', self.events.process_raw, results[5]),
        ]

        for name, handler, data in handlers_data:
            if isinstance(data, BaseException):
                logger.warning('Failed to fetch %s: %s', name, data)
            else:
                handler(data)
                logger.debug('Loaded %d %s', len(data), name)

        # Sites use a global endpoint
        try:
            sites_data = await fetch('/api/self/sites')
            self.sites.process_full(sites_data)
            logger.debug('Loaded %d sites', len(sites_data))
        except Exception as e:
            logger.warning('Failed to fetch sites: %s', e)

    # --- WebSocket ---

    async def start(self) -> None:
        """Start the WebSocket listener. Blocks until disconnected or error."""
        assert self._http is not None
        session_cookie = self._get_session_cookie()
        self._ws = WebSocketClient(
            host=self._config.host,
            port=self._config.port,
            site=self._config.site,
            session_cookie=session_cookie,
            is_unifi_os=self._session.is_unifi_os,
            ssl_verify=self._config.ssl_verify,
        )
        await self._ws.connect()

        try:
            async for message in self._ws.listen():
                key = message.meta.message_key
                handler = self._ws_handlers.get(key)
                if handler:
                    handler(message.data)
                else:
                    logger.debug('Unhandled WebSocket message key: %s', key)
        except Exception as e:
            logger.error('WebSocket error: %s', e)
            raise
        finally:
            await self._ws.close()

    def _get_session_cookie(self) -> str:
        """Extract the session cookie from the HTTP transport."""
        assert self._http is not None
        client = self._http._client
        if client and client.cookies:
            token = client.cookies.get('TOKEN')
            if token:
                return str(token)
        return ''

    async def refresh_devices(self) -> None:
        """Re-fetch device data from the controller."""
        assert self._http is not None
        is_os = self._session.is_unifi_os
        site = self._config.site
        path = f'/proxy/network/api/s/{site}/stat/device' if is_os else f'/api/s/{site}/stat/device'
        resp = await self._http.get(path)
        data: list[dict] = resp.json().get('data', [])
        self.devices.process_full(data)

    # --- API actions ---

    async def request(self, method: str, path: str, data: dict | None = None) -> list[dict]:
        """Execute an API request and return the data array."""
        assert self._http is not None
        is_os = self._session.is_unifi_os
        full_path = f'/proxy/network{path}' if is_os else path
        full_path = full_path.format(site=self._config.site)

        resp = await self._http.request(method, full_path, json=data)
        body = resp.json()
        if isinstance(body, dict):
            result: list[dict] = body.get('data', [])
            return result
        return []

    async def execute(self, request_obj: object) -> list[dict]:
        """Execute an ApiRequest or ApiRequestV2 and return the data array.

        Accepts any object with ``method``, ``data``, and ``full_path(site, is_unifi_os)`` attributes.
        """
        method = getattr(request_obj, 'method', 'GET')
        data = getattr(request_obj, 'data', None)
        full_path_fn = getattr(request_obj, 'full_path', None)
        if full_path_fn is None:
            raise TypeError(f'{type(request_obj).__name__} has no full_path method')

        path = full_path_fn(self._config.site, self._session.is_unifi_os)
        assert self._http is not None
        resp = await self._http.request(method, path, json=data)
        body = resp.json()
        if isinstance(body, dict):
            result: list[dict] = body.get('data', [])
            return result
        return []

    # --- Cleanup ---

    async def disconnect(self) -> None:
        """Disconnect from the controller and clean up resources."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http:
            await self._http.close()
            self._http = None

    async def __aenter__(self) -> Controller:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()
