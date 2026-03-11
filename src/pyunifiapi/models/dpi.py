"""DPI restriction app and group models with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class DPIRestrictionApp(ApiItem):
    """A DPI restriction application rule."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    @property
    def apps(self) -> list[str]:
        return self.raw.get('apps', [])

    @property
    def cats(self) -> list[str]:
        return self.raw.get('cats', [])

    @property
    def blocked(self) -> bool:
        return self.raw.get('blocked', False)

    @property
    def enabled(self) -> bool:
        return self.raw.get('enabled', False)

    @property
    def log(self) -> bool:
        return self.raw.get('log', False)


@final
class DPIRestrictionGroup(ApiItem):
    """A DPI restriction group containing app rules."""

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
    def dpiapp_ids(self) -> list[str]:
        return self.raw.get('dpiapp_ids', [])

    @property
    def no_delete(self) -> bool:
        return self.raw.get('attr_no_delete', False)

    @property
    def hidden_id(self) -> str:
        return self.raw.get('attr_hidden_id', '')


# --- Request classes ---


@dataclass(frozen=True)
class DPIRestrictionAppListRequest(ApiRequest):
    """GET /api/s/{site}/rest/dpiapp - list DPI restriction apps."""

    method: str = 'GET'
    path: str = '/api/s/{site}/rest/dpiapp'


@dataclass(frozen=True)
class DPIRestrictionAppEnableRequest(ApiRequest):
    """PUT /api/s/{site}/rest/dpiapp/{id} - enable or disable a DPI app rule."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/dpiapp/{app_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, app: DPIRestrictionApp, enabled: bool) -> DPIRestrictionAppEnableRequest:
        path = f'/api/s/{{site}}/rest/dpiapp/{app.id}'
        return cls(path=path, data={'enabled': enabled})


@dataclass(frozen=True)
class DPIRestrictionGroupListRequest(ApiRequest):
    """GET /api/s/{site}/rest/dpigroup - list DPI restriction groups."""

    method: str = 'GET'
    path: str = '/api/s/{site}/rest/dpigroup'
