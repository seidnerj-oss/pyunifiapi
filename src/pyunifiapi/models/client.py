"""Client model with typed properties and request classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class Client(ApiItem):
    """An active network client (wired or wireless)."""

    # --- Identity ---

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def mac(self) -> str:
        return self.raw.get('mac', '')

    @property
    def name(self) -> str:
        """Display name (user-set name, hostname, or MAC)."""
        return self.raw.get('name', self.raw.get('hostname', self.mac))

    @property
    def hostname(self) -> str:
        return self.raw.get('hostname', '')

    @property
    def oui(self) -> str:
        return self.raw.get('oui', '')

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    # --- Network ---

    @property
    def ip(self) -> str:
        return self.raw.get('ip', '')

    @property
    def fixed_ip(self) -> str:
        return self.raw.get('fixed_ip', '')

    @property
    def use_fixed_ip(self) -> bool:
        return self.raw.get('use_fixedip', False)

    @property
    def network(self) -> str:
        return self.raw.get('network', '')

    @property
    def network_id(self) -> str:
        return self.raw.get('network_id', '')

    @property
    def vlan(self) -> int:
        return self.raw.get('vlan', 0)

    # --- Connection type ---

    @property
    def is_wired(self) -> bool:
        return self.raw.get('is_wired', False)

    @property
    def is_guest(self) -> bool:
        return self.raw.get('is_guest', False)

    @property
    def is_authorized(self) -> bool:
        return self.raw.get('authorized', False)

    @property
    def blocked(self) -> bool:
        return self.raw.get('blocked', False)

    # --- Connected device ---

    @property
    def ap_mac(self) -> str:
        """MAC of the AP this client is connected to (wireless)."""
        return self.raw.get('ap_mac', '')

    @property
    def sw_mac(self) -> str:
        """MAC of the switch this client is connected to (wired)."""
        return self.raw.get('sw_mac', '')

    @property
    def gw_mac(self) -> str:
        return self.raw.get('gw_mac', '')

    @property
    def sw_port(self) -> int:
        return self.raw.get('sw_port', 0)

    # --- Wireless ---

    @property
    def essid(self) -> str:
        return self.raw.get('essid', '')

    @property
    def bssid(self) -> str:
        return self.raw.get('bssid', '')

    @property
    def channel(self) -> int:
        return self.raw.get('channel', 0)

    @property
    def radio(self) -> str:
        return self.raw.get('radio', '')

    @property
    def radio_proto(self) -> str:
        return self.raw.get('radio_proto', '')

    @property
    def signal(self) -> int:
        return self.raw.get('signal', 0)

    @property
    def noise(self) -> int:
        return self.raw.get('noise', 0)

    @property
    def rssi(self) -> int:
        return self.raw.get('rssi', 0)

    @property
    def satisfaction(self) -> int:
        return self.raw.get('satisfaction', 0)

    @property
    def tx_rate(self) -> int:
        return self.raw.get('tx_rate', 0)

    @property
    def rx_rate(self) -> int:
        return self.raw.get('rx_rate', 0)

    @property
    def ccq(self) -> int:
        return self.raw.get('ccq', 0)

    @property
    def powersave_enabled(self) -> bool:
        return self.raw.get('powersave_enabled', False)

    # --- Statistics ---

    @property
    def uptime(self) -> int:
        return self.raw.get('uptime', 0)

    @property
    def idle_time(self) -> int:
        return self.raw.get('idletime', 0)

    @property
    def first_seen(self) -> int:
        return self.raw.get('first_seen', 0)

    @property
    def last_seen(self) -> int:
        return self.raw.get('last_seen', 0)

    @property
    def assoc_time(self) -> int:
        return self.raw.get('assoc_time', 0)

    @property
    def rx_bytes(self) -> int:
        return self.raw.get('rx_bytes', 0)

    @property
    def tx_bytes(self) -> int:
        return self.raw.get('tx_bytes', 0)

    @property
    def rx_packets(self) -> int:
        return self.raw.get('rx_packets', 0)

    @property
    def tx_packets(self) -> int:
        return self.raw.get('tx_packets', 0)

    @property
    def bytes_r(self) -> int:
        return self.raw.get('bytes-r', 0)

    # --- Device info ---

    @property
    def device_name(self) -> str:
        return self.raw.get('device_name', '')

    @property
    def fw_version(self) -> str:
        return self.raw.get('fw_version', '')

    @property
    def dev_vendor(self) -> int:
        return self.raw.get('dev_vendor', 0)

    @property
    def os_name(self) -> str:
        return self.raw.get('os_name', '')

    @property
    def dev_cat(self) -> int:
        return self.raw.get('dev_cat', 0)

    @property
    def dev_family(self) -> int:
        return self.raw.get('dev_family', 0)

    @property
    def noted(self) -> bool:
        return self.raw.get('noted', False)

    @property
    def note(self) -> str:
        return self.raw.get('note', '')

    @property
    def qos_policy_applied(self) -> bool:
        return self.raw.get('qos_policy_applied', False)


# --- Request classes ---


@dataclass(frozen=True)
class ClientListRequest(ApiRequest):
    """GET /api/s/{site}/stat/sta - list active clients."""

    method: str = 'GET'
    path: str = '/api/s/{site}/stat/sta'


@dataclass(frozen=True)
class AllClientListRequest(ApiRequest):
    """GET /api/s/{site}/stat/alluser - list all known clients (active + historical)."""

    method: str = 'GET'
    path: str = '/api/s/{site}/stat/alluser'


@dataclass(frozen=True)
class ClientBlockRequest(ApiRequest):
    """POST /api/s/{site}/cmd/stamgr - block a client."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/stamgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str) -> ClientBlockRequest:
        return cls(data={'cmd': 'block-sta', 'mac': mac.lower()})


@dataclass(frozen=True)
class ClientUnblockRequest(ApiRequest):
    """POST /api/s/{site}/cmd/stamgr - unblock a client."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/stamgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str) -> ClientUnblockRequest:
        return cls(data={'cmd': 'unblock-sta', 'mac': mac.lower()})


@dataclass(frozen=True)
class ClientReconnectRequest(ApiRequest):
    """POST /api/s/{site}/cmd/stamgr - force a client to reconnect."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/stamgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str) -> ClientReconnectRequest:
        return cls(data={'cmd': 'kick-sta', 'mac': mac.lower()})


@dataclass(frozen=True)
class ClientRemoveRequest(ApiRequest):
    """POST /api/s/{site}/cmd/stamgr - remove clients."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/stamgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, macs: list[str]) -> ClientRemoveRequest:
        return cls(data={'cmd': 'forget-sta', 'macs': [m.lower() for m in macs]})
