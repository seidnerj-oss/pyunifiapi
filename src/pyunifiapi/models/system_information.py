"""System information model with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class SystemInformation(ApiItem):
    """Controller system information."""

    @property
    def anonymous_controller_id(self) -> str:
        return self.raw.get('anonymous_controller_id', '')

    @property
    def device_type(self) -> str:
        return self.raw.get('ubnt_device_type', '')

    @property
    def hostname(self) -> str:
        return self.raw.get('hostname', '')

    @property
    def ip_address(self) -> list[str]:
        return self.raw.get('ip_addrs', [])

    @property
    def is_cloud_console(self) -> bool:
        return self.raw.get('is_cloud_console', False)

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def previous_version(self) -> str:
        return self.raw.get('previous_version', '')

    @property
    def update_available(self) -> bool:
        return self.raw.get('update_available', False)

    @property
    def uptime(self) -> int:
        return self.raw.get('uptime', 0)

    @property
    def version(self) -> str:
        return self.raw.get('version', '')

    @property
    def build(self) -> str:
        return self.raw.get('build', '')


# --- Request classes ---


@dataclass(frozen=True)
class SystemInformationRequest(ApiRequest):
    """GET /api/s/{site}/stat/sysinfo - get system information."""

    method: str = 'GET'
    path: str = '/api/s/{site}/stat/sysinfo'
