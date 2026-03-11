"""WLAN configuration model with typed properties and request classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class Wlan(ApiItem):
    """A WLAN (wireless network) configuration."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    @property
    def enabled(self) -> bool:
        return self.raw.get('enabled', False)

    @property
    def security(self) -> str:
        return self.raw.get('security', '')

    @property
    def wpa_mode(self) -> str:
        return self.raw.get('wpa_mode', '')

    @property
    def wpa_enc(self) -> str:
        return self.raw.get('wpa_enc', '')

    @property
    def passphrase(self) -> str:
        return self.raw.get('x_passphrase', '')

    @property
    def hide_ssid(self) -> bool:
        return self.raw.get('hide_ssid', False)

    @property
    def is_guest(self) -> bool:
        return self.raw.get('is_guest', False)

    @property
    def mac_filter_enabled(self) -> bool:
        return self.raw.get('mac_filter_enabled', False)

    @property
    def mac_filter_policy(self) -> str:
        return self.raw.get('mac_filter_policy', 'deny')

    @property
    def mac_filter_list(self) -> list[str]:
        return self.raw.get('mac_filter_list', [])

    @property
    def bc_filter_enabled(self) -> bool:
        return self.raw.get('bc_filter_enabled', False)

    @property
    def bc_filter_list(self) -> list[str]:
        return self.raw.get('bc_filter_list', [])

    @property
    def group_rekey(self) -> int:
        return self.raw.get('group_rekey', 0)

    @property
    def dtim_mode(self) -> str:
        return self.raw.get('dtim_mode', 'default')

    @property
    def dtim_na(self) -> int:
        return self.raw.get('dtim_na', 1)

    @property
    def dtim_ng(self) -> int:
        return self.raw.get('dtim_ng', 1)

    @property
    def schedule(self) -> list[dict[str, Any]]:
        return self.raw.get('schedule', [])

    @property
    def schedule_enabled(self) -> bool:
        return self.raw.get('schedule_enabled', False)

    @property
    def usergroup_id(self) -> str:
        return self.raw.get('usergroup_id', '')

    @property
    def wlangroup_id(self) -> str:
        return self.raw.get('wlangroup_id', '')

    @property
    def name_combine_enabled(self) -> bool:
        return self.raw.get('name_combine_enabled', False)

    @property
    def name_combine_suffix(self) -> str:
        return self.raw.get('name_combine_suffix', '')


# --- Request classes ---


@dataclass(frozen=True)
class WlanListRequest(ApiRequest):
    """GET /api/s/{site}/rest/wlanconf - list WLAN configurations."""

    method: str = 'GET'
    path: str = '/api/s/{site}/rest/wlanconf'


@dataclass(frozen=True)
class WlanEnableRequest(ApiRequest):
    """PUT /api/s/{site}/rest/wlanconf/{id} - enable or disable a WLAN."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/wlanconf/{wlan_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, wlan: Wlan, enabled: bool) -> WlanEnableRequest:
        path = f'/api/s/{{site}}/rest/wlanconf/{wlan.id}'
        return cls(path=path, data={'enabled': enabled})


@dataclass(frozen=True)
class WlanChangePasswordRequest(ApiRequest):
    """PUT /api/s/{site}/rest/wlanconf/{id} - change WLAN passphrase."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/wlanconf/{wlan_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, wlan: Wlan, passphrase: str) -> WlanChangePasswordRequest:
        path = f'/api/s/{{site}}/rest/wlanconf/{wlan.id}'
        return cls(path=path, data={'x_passphrase': passphrase})
