"""Device model with typed properties and request classes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


class DeviceState(IntEnum):
    """Device adoption/connection state."""

    DISCONNECTED = 0
    CONNECTED = 1
    PENDING_ADOPTION = 2
    FIRMWARE_MISMATCH = 3
    UPGRADING = 4
    PROVISIONING = 5
    HEARTBEAT_MISSED = 6
    ADOPTING = 7
    DELETING = 8
    MANAGED_BY_OTHER = 9
    ADOPTING_WIRELESS = 10
    RESTORING = 11


class HardwareCapability(IntFlag):
    """Device hardware capability flags."""

    LED_RING = 0x4


@final
class Device(ApiItem):
    """A UniFi managed device (AP, switch, gateway, etc.)."""

    # --- Identity ---

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def mac(self) -> str:
        return self.raw.get('mac', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def model(self) -> str:
        return self.raw.get('model', '')

    @property
    def type(self) -> str:
        """Device type: uap, usw, ugw, udm, etc."""
        return self.raw.get('type', '')

    @property
    def serial(self) -> str:
        return self.raw.get('serial', '')

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    # --- Versioning ---

    @property
    def board_rev(self) -> int:
        return self.raw.get('board_rev', 0)

    @property
    def hw_version(self) -> str:
        """Hardware version (board_rev as string or direct hw_ver field)."""
        return str(self.raw.get('hw_ver', self.raw.get('board_rev', '')))

    @property
    def fw_version(self) -> str:
        return self.raw.get('version', '')

    @property
    def required_version(self) -> str:
        return self.raw.get('required_version', '')

    # --- State ---

    @property
    def state(self) -> DeviceState:
        return DeviceState(self.raw.get('state', 0))

    @property
    def adopted(self) -> bool:
        return self.raw.get('adopted', False)

    @property
    def disabled(self) -> bool:
        return self.raw.get('disabled', False)

    @property
    def unsupported(self) -> bool:
        return self.raw.get('unsupported', False)

    @property
    def unsupported_reason(self) -> int:
        return self.raw.get('unsupported_reason', 0)

    @property
    def uptime(self) -> int:
        return self.raw.get('uptime', 0)

    @property
    def last_seen(self) -> int:
        return self.raw.get('last_seen', 0)

    @property
    def upgradable(self) -> bool:
        return self.raw.get('upgradable', False)

    @property
    def upgrade_to_firmware(self) -> str:
        return self.raw.get('upgrade_to_firmware', '')

    # --- Network ---

    @property
    def ip(self) -> str:
        return self.raw.get('ip', '')

    @property
    def inform_url(self) -> str:
        return self.raw.get('inform_url', '')

    @property
    def inform_ip(self) -> str:
        return self.raw.get('inform_ip', '')

    # --- Statistics ---

    @property
    def bytes_d(self) -> int:
        return self.raw.get('bytes-d', 0)

    @property
    def bytes_r(self) -> int:
        return self.raw.get('bytes-r', 0)

    @property
    def rx_bytes(self) -> int:
        return self.raw.get('rx_bytes', 0)

    @property
    def tx_bytes(self) -> int:
        return self.raw.get('tx_bytes', 0)

    @property
    def connected_clients(self) -> int:
        return self.raw.get('num_sta', 0)

    @property
    def guest_clients(self) -> int:
        return self.raw.get('guest-num_sta', 0)

    # --- LED ---

    @property
    def led_override(self) -> str:
        """LED override state: 'default', 'on', or 'off'."""
        return self.raw.get('led_override', 'default')

    @property
    def led_override_color(self) -> str:
        return self.raw.get('led_override_color', '')

    @property
    def led_override_color_brightness(self) -> int:
        return self.raw.get('led_override_color_brightness', 100)

    @property
    def supports_led_ring(self) -> bool:
        """Whether this device has an LED ring that supports color and brightness."""
        hw_caps = self.raw.get('hw_caps', 0)
        return bool(hw_caps & HardwareCapability.LED_RING)

    # --- Port and outlet tables ---

    @property
    def port_table(self) -> list[dict[str, Any]]:
        return self.raw.get('port_table', [])

    @property
    def outlet_table(self) -> list[dict[str, Any]]:
        return self.raw.get('outlet_table', [])

    # --- Wireless ---

    @property
    def radio_table(self) -> list[dict[str, Any]]:
        return self.raw.get('radio_table', [])

    @property
    def wlan_overrides(self) -> list[dict[str, Any]]:
        return self.raw.get('wlan_overrides', [])

    # --- System stats ---

    @property
    def system_stats(self) -> dict[str, Any]:
        return self.raw.get('system-stats', {})

    @property
    def cpu_usage(self) -> float:
        return float(self.system_stats.get('cpu', '0'))

    @property
    def mem_usage(self) -> float:
        return float(self.system_stats.get('mem', '0'))

    @property
    def loadavg_1(self) -> float:
        return float(self.raw.get('sys_stats', {}).get('loadavg_1', '0'))

    @property
    def loadavg_5(self) -> float:
        return float(self.raw.get('sys_stats', {}).get('loadavg_5', '0'))

    @property
    def loadavg_15(self) -> float:
        return float(self.raw.get('sys_stats', {}).get('loadavg_15', '0'))

    # --- Uplink ---

    @property
    def uplink(self) -> dict[str, Any]:
        return self.raw.get('uplink', {})

    @property
    def uplink_type(self) -> str:
        return self.uplink.get('type', '')

    @property
    def uplink_speed(self) -> int:
        return self.uplink.get('speed', 0)

    @property
    def downlink_speed(self) -> int:
        return self.raw.get('uplink', {}).get('max_speed', 0)

    # --- Temperatures ---

    @property
    def temperatures(self) -> list[dict[str, Any]]:
        return self.raw.get('temperatures', [])

    # --- Power ---

    @property
    def power_source(self) -> str:
        return self.raw.get('power_source', '')

    # --- Location ---

    @property
    def x(self) -> float:
        return self.raw.get('x', 0.0)

    @property
    def y(self) -> float:
        return self.raw.get('y', 0.0)

    @property
    def outdoor_mode(self) -> bool:
        return self.raw.get('outdoor_mode_override', '') == 'on'

    # --- Misc ---

    @property
    def model_in_eol(self) -> bool:
        return self.raw.get('model_in_eol', False)

    @property
    def model_in_lts(self) -> bool:
        return self.raw.get('model_in_lts', False)

    @property
    def satisfaction(self) -> int:
        return self.raw.get('satisfaction', 0)

    @property
    def speedtest_status(self) -> dict[str, Any]:
        return self.raw.get('speedtest-status', {})

    @property
    def config_network(self) -> dict[str, Any]:
        return self.raw.get('config_network', {})

    @property
    def ethernet_table(self) -> list[dict[str, Any]]:
        return self.raw.get('ethernet_table', [])


# --- Request classes ---


@dataclass(frozen=True)
class DeviceListRequest(ApiRequest):
    """GET /api/s/{site}/stat/device - list all devices."""

    method: str = 'GET'
    path: str = '/api/s/{site}/stat/device'


@dataclass(frozen=True)
class DeviceRestartRequest(ApiRequest):
    """POST /api/s/{site}/cmd/devmgr - restart a device."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/devmgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str) -> DeviceRestartRequest:
        return cls(data={'cmd': 'restart', 'mac': mac.lower()})


@dataclass(frozen=True)
class DeviceUpgradeRequest(ApiRequest):
    """POST /api/s/{site}/cmd/devmgr - upgrade device firmware."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/devmgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str) -> DeviceUpgradeRequest:
        return cls(data={'cmd': 'upgrade', 'mac': mac.lower()})


@dataclass(frozen=True)
class DeviceLocateRequest(ApiRequest):
    """POST /api/s/{site}/cmd/devmgr - toggle device locate LED."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/devmgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str, locate: bool = True) -> DeviceLocateRequest:
        cmd = 'set-locate' if locate else 'unset-locate'
        return cls(data={'cmd': cmd, 'mac': mac.lower()})


@dataclass(frozen=True)
class DevicePowerCyclePortRequest(ApiRequest):
    """POST /api/s/{site}/cmd/devmgr - power cycle a PoE port."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/devmgr'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, mac: str, port_idx: int) -> DevicePowerCyclePortRequest:
        return cls(data={'cmd': 'power-cycle', 'mac': mac.lower(), 'port_idx': port_idx})


@dataclass(frozen=True)
class DeviceSetLedStatus(ApiRequest):
    """PUT /api/s/{site}/rest/device/{id} - set LED override."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/device/{device_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        device: Device,
        status: str = 'on',
        color: str | None = None,
        brightness: int | None = None,
    ) -> DeviceSetLedStatus:
        """Create an LED status request.

        Args:
            device: The target device.
            status: 'on', 'off', or 'default'.
            color: Hex color string (e.g. '#0000FF'). Only for LED ring devices.
            brightness: Brightness 0-100. Only for LED ring devices.
        """
        payload: dict[str, Any] = {'led_override': status}
        if color is not None:
            payload['led_override_color'] = color
        if brightness is not None:
            payload['led_override_color_brightness'] = brightness
        path = f'/api/s/{{site}}/rest/device/{device.id}'
        return cls(path=path, data=payload)


@dataclass(frozen=True)
class DeviceSetPoePortModeRequest(ApiRequest):
    """PUT /api/s/{site}/rest/device/{id} - set PoE mode on a port."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/device/{device_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, device: Device, port_idx: int, poe_mode: str) -> DeviceSetPoePortModeRequest:
        overrides = list(device.raw.get('port_overrides', []))
        found = False
        for override in overrides:
            if override.get('port_idx') == port_idx:
                override['poe_mode'] = poe_mode
                found = True
                break
        if not found:
            overrides.append({'port_idx': port_idx, 'poe_mode': poe_mode})
        path = f'/api/s/{{site}}/rest/device/{device.id}'
        return cls(path=path, data={'port_overrides': overrides})


@dataclass(frozen=True)
class DeviceSetOutletRelayRequest(ApiRequest):
    """PUT /api/s/{site}/rest/device/{id} - set outlet relay state."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/device/{device_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, device: Device, outlet_idx: int, relay_state: bool) -> DeviceSetOutletRelayRequest:
        overrides = list(device.raw.get('outlet_overrides', []))
        found = False
        for override in overrides:
            if override.get('index') == outlet_idx:
                override['relay_state'] = relay_state
                found = True
                break
        if not found:
            overrides.append({'index': outlet_idx, 'relay_state': relay_state})
        path = f'/api/s/{{site}}/rest/device/{device.id}'
        return cls(path=path, data={'outlet_overrides': overrides})
