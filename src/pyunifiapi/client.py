"""UniFi controller REST API client (local mode)."""

from __future__ import annotations

import logging

from pyunifiapi._constants import (
    API_CMD_DEVMGR,
    API_CMD_STAMGR,
    API_GET_SETTING,
    API_LIST_NETWORKCONF,
    API_LIST_PORTCONF,
    API_LIST_PORTFORWARD,
    API_LIST_WLANCONF,
    API_LIST_WLANGROUP,
    API_SELF_SITES,
    API_STAT_ALARM,
    API_STAT_ALLUSER,
    API_STAT_DASHBOARD,
    API_STAT_DEVICE,
    API_STAT_EVENT,
    API_STAT_GUEST,
    API_STAT_HEALTH,
    API_STAT_ROGUEAP,
    API_STAT_SESSIONS,
    API_STAT_SITES,
    API_STAT_STA,
    API_STAT_SYSINFO,
)
from pyunifiapi._types import ControllerConfig, SSHConfig
from pyunifiapi.http._local import LocalHttpTransport
from pyunifiapi.ssh.session import SSHSession

logger = logging.getLogger(__name__)


class UnifiClient:
    """UniFi controller REST API client.

    Provides methods for querying and managing devices, clients,
    networks, and other controller resources via the local REST API.

    Usage::

        async with UnifiClient(config) as client:
            devices = await client.list_devices()
            for d in devices:
                print(d['name'], d['mac'])
    """

    def __init__(self, config: ControllerConfig) -> None:
        self._config = config
        self._http: LocalHttpTransport | None = None

    async def __aenter__(self) -> UnifiClient:
        self._http = LocalHttpTransport(self._config)
        await self._http.login()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _path(self, template: str) -> str:
        """Format an API path template with the configured site."""
        return template.format(site=self._config.site)

    async def _get_data(self, path_template: str, suffix: str = '') -> list[dict]:
        """GET a path and return the 'data' array from the response."""
        assert self._http is not None
        path = self._path(path_template) + suffix
        resp = await self._http.get(path)
        result: list[dict] = resp.json().get('data', [])
        return result

    async def _post_cmd(self, path_template: str, payload: dict) -> list[dict]:
        """POST a command and return the 'data' array from the response."""
        assert self._http is not None
        resp = await self._http.post(self._path(path_template), json=payload)
        result: list[dict] = resp.json().get('data', [])
        return result

    # --- Device management ---

    async def list_devices(self) -> list[dict]:
        """List all devices managed by the controller."""
        return await self._get_data(API_STAT_DEVICE)

    async def get_device(self, mac: str) -> dict | None:
        """Get a specific device by MAC address."""
        data = await self._get_data(API_STAT_DEVICE, suffix=f'/{mac}')
        return data[0] if data else None

    async def restart_device(self, mac: str) -> list[dict]:
        """Restart (reboot) a device."""
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': 'restart', 'mac': mac.lower()})

    async def adopt_device(self, mac: str) -> list[dict]:
        """Adopt a device to this site."""
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': 'adopt', 'mac': mac.lower()})

    async def force_provision(self, mac: str) -> list[dict]:
        """Force re-provision a device."""
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': 'force-provision', 'mac': mac.lower()})

    async def set_locate(self, mac: str, enabled: bool = True) -> list[dict]:
        """Toggle device locate LED."""
        cmd = 'set-locate' if enabled else 'unset-locate'
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': cmd, 'mac': mac.lower()})

    async def upgrade_device(self, mac: str, url: str | None = None) -> list[dict]:
        """Upgrade device firmware."""
        payload: dict = {'cmd': 'upgrade', 'mac': mac.lower()}
        if url:
            payload['cmd'] = 'upgrade-external'
            payload['url'] = url
        return await self._post_cmd(API_CMD_DEVMGR, payload)

    async def power_cycle_port(self, mac: str, port_idx: int) -> list[dict]:
        """Power cycle a PoE switch port."""
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': 'power-cycle', 'mac': mac.lower(), 'port_idx': port_idx})

    async def speedtest(self, mac: str) -> list[dict]:
        """Run a speed test on a device."""
        return await self._post_cmd(API_CMD_DEVMGR, {'cmd': 'speedtest', 'mac': mac.lower()})

    # --- Client management ---

    async def list_clients(self) -> list[dict]:
        """List all active clients."""
        return await self._get_data(API_STAT_STA)

    async def list_all_users(self) -> list[dict]:
        """List all known users (active and historical)."""
        return await self._get_data(API_STAT_ALLUSER)

    async def list_guests(self) -> list[dict]:
        """List active guest clients."""
        return await self._get_data(API_STAT_GUEST)

    async def block_client(self, mac: str) -> list[dict]:
        """Block a client."""
        return await self._post_cmd(API_CMD_STAMGR, {'cmd': 'block-sta', 'mac': mac.lower()})

    async def unblock_client(self, mac: str) -> list[dict]:
        """Unblock a client."""
        return await self._post_cmd(API_CMD_STAMGR, {'cmd': 'unblock-sta', 'mac': mac.lower()})

    async def reconnect_client(self, mac: str) -> list[dict]:
        """Force a client to reconnect."""
        return await self._post_cmd(API_CMD_STAMGR, {'cmd': 'kick-sta', 'mac': mac.lower()})

    async def authorize_guest(self, mac: str, minutes: int = 60) -> list[dict]:
        """Authorize a guest client."""
        return await self._post_cmd(API_CMD_STAMGR, {'cmd': 'authorize-guest', 'mac': mac.lower(), 'minutes': minutes})

    async def unauthorize_guest(self, mac: str) -> list[dict]:
        """Revoke guest authorization."""
        return await self._post_cmd(API_CMD_STAMGR, {'cmd': 'unauthorize-guest', 'mac': mac.lower()})

    # --- Site ---

    async def list_sites(self) -> list[dict]:
        """List all sites accessible to the current user."""
        assert self._http is not None
        resp = await self._http.get(API_SELF_SITES)
        result: list[dict] = resp.json().get('data', [])
        return result

    async def get_site_stats(self) -> list[dict]:
        """Get site statistics."""
        assert self._http is not None
        resp = await self._http.get(API_STAT_SITES)
        result: list[dict] = resp.json().get('data', [])
        return result

    async def get_settings(self) -> list[dict]:
        """Get all site settings."""
        return await self._get_data(API_GET_SETTING)

    # --- Network / WLAN ---

    async def list_wlan_conf(self) -> list[dict]:
        """List WLAN configurations."""
        return await self._get_data(API_LIST_WLANCONF)

    async def list_wlan_groups(self) -> list[dict]:
        """List WLAN groups."""
        return await self._get_data(API_LIST_WLANGROUP)

    async def list_network_conf(self) -> list[dict]:
        """List network configurations."""
        return await self._get_data(API_LIST_NETWORKCONF)

    async def list_port_conf(self) -> list[dict]:
        """List port configurations."""
        return await self._get_data(API_LIST_PORTCONF)

    async def list_port_forwards(self) -> list[dict]:
        """List port forwarding rules."""
        return await self._get_data(API_LIST_PORTFORWARD)

    # --- Statistics ---

    async def get_sysinfo(self) -> list[dict]:
        """Get system information."""
        return await self._get_data(API_STAT_SYSINFO)

    async def get_health(self) -> list[dict]:
        """Get site health metrics."""
        return await self._get_data(API_STAT_HEALTH)

    async def get_dashboard(self) -> list[dict]:
        """Get dashboard statistics."""
        return await self._get_data(API_STAT_DASHBOARD)

    async def get_events(self, count: int = 3000) -> list[dict]:
        """Get recent events."""
        assert self._http is not None
        resp = await self._http.get(self._path(API_STAT_EVENT) + f'?_limit={count}')
        result: list[dict] = resp.json().get('data', [])
        return result

    async def get_alarms(self) -> list[dict]:
        """Get active alarms."""
        return await self._get_data(API_STAT_ALARM)

    async def get_sessions(self) -> list[dict]:
        """Get active sessions."""
        return await self._get_data(API_STAT_SESSIONS)

    async def get_rogue_aps(self) -> list[dict]:
        """Get detected rogue access points."""
        return await self._get_data(API_STAT_ROGUEAP)

    # --- SSH ---

    def ssh(self, ssh_config: SSHConfig) -> SSHSession:
        """Create an SSH session to a device through this controller.

        Returns an SSHSession that should be used as an async context manager::

            async with client.ssh(SSHConfig(mac='aa:bb:cc:dd:ee:ff')) as ssh:
                output = await ssh.execute('uptime')
        """
        return SSHSession(controller=self._config, ssh=ssh_config)

    # --- Cleanup ---

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._http:
            await self._http.close()
            self._http = None
