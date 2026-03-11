"""Network port model (derived from device port_table)."""

from __future__ import annotations

from typing import Any, final

from pyunifiapi.models.api import ApiItem


@final
class Port(ApiItem):
    """A network port on a UniFi switch or gateway."""

    @property
    def ifname(self) -> str:
        return self.raw.get('ifname', '')

    @property
    def name(self) -> str:
        name = self.raw.get('name', '')
        return name if name else f'Port {self.port_idx}'

    @property
    def port_idx(self) -> int:
        return self.raw.get('port_idx', 0)

    @property
    def media(self) -> str:
        return self.raw.get('media', '')

    @property
    def up(self) -> bool:
        return self.raw.get('up', False)

    @property
    def enabled(self) -> bool:
        return self.raw.get('enable', False)

    @property
    def speed(self) -> int:
        return self.raw.get('speed', 0)

    @property
    def full_duplex(self) -> bool:
        return self.raw.get('full_duplex', False)

    @property
    def portconf_id(self) -> str:
        return self.raw.get('portconf_id', '')

    # --- PoE ---

    @property
    def poe_caps(self) -> int:
        """PoE capability flags: 0=none, 3=auto, 7=24V, 8=passthrough, 35=all."""
        return self.raw.get('poe_caps', 0)

    @property
    def poe_enable(self) -> bool:
        return self.raw.get('poe_enable', False)

    @property
    def poe_mode(self) -> str:
        return self.raw.get('poe_mode', '')

    @property
    def poe_class(self) -> str:
        return self.raw.get('poe_class', '')

    @property
    def poe_power(self) -> float:
        return float(self.raw.get('poe_power', '0'))

    @property
    def poe_voltage(self) -> float:
        return float(self.raw.get('poe_voltage', '0'))

    @property
    def port_poe(self) -> bool:
        return self.raw.get('port_poe', False)

    # --- Traffic ---

    @property
    def rx_bytes(self) -> int:
        return self.raw.get('rx_bytes', 0)

    @property
    def rx_bytes_r(self) -> int:
        return self.raw.get('rx_bytes-r', 0)

    @property
    def tx_bytes(self) -> int:
        return self.raw.get('tx_bytes', 0)

    @property
    def tx_bytes_r(self) -> int:
        return self.raw.get('tx_bytes-r', 0)

    # --- Composite ID for handler keying ---

    @property
    def port_id(self) -> str:
        """Composite ID: device_mac-port_idx."""
        mac = self.raw.get('_device_mac', '')
        return f'{mac}-{self.port_idx}'

    def with_device_mac(self, mac: str) -> Port:
        """Return a copy with the parent device MAC injected."""
        new_raw: dict[str, Any] = {**self.raw, '_device_mac': mac}
        return Port(new_raw)
