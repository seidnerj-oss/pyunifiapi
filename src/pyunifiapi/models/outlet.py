"""Power outlet model (derived from device outlet_table)."""

from __future__ import annotations

from typing import Any, final

from pyunifiapi.models.api import ApiItem


@final
class Outlet(ApiItem):
    """A power outlet on a UniFi power distribution device."""

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def index(self) -> int:
        return self.raw.get('index', 0)

    @property
    def caps(self) -> int:
        """Capability flags: 1=relay, 3=relay+metering."""
        return self.raw.get('outlet_caps', 0)

    @property
    def has_relay(self) -> bool:
        return bool(self.caps & 1)

    @property
    def relay_state(self) -> bool:
        return self.raw.get('relay_state', False)

    @property
    def cycle_enabled(self) -> bool:
        return self.raw.get('cycle_enabled', False)

    @property
    def has_metering(self) -> bool:
        return bool(self.caps & 2)

    @property
    def voltage(self) -> float:
        return float(self.raw.get('outlet_voltage', '0'))

    @property
    def current(self) -> float:
        return float(self.raw.get('outlet_current', '0'))

    @property
    def power(self) -> float:
        return float(self.raw.get('outlet_power', '0'))

    @property
    def power_factor(self) -> float:
        return float(self.raw.get('outlet_power_factor', '0'))

    # --- Composite ID for handler keying ---

    @property
    def outlet_id(self) -> str:
        """Composite ID: device_mac-index."""
        mac = self.raw.get('_device_mac', '')
        return f'{mac}-{self.index}'

    def with_device_mac(self, mac: str) -> Outlet:
        """Return a copy with the parent device MAC injected."""
        new_raw: dict[str, Any] = {**self.raw, '_device_mac': mac}
        return Outlet(new_raw)
