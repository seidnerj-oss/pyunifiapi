"""Site model with typed properties and request classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class Site(ApiItem):
    """A UniFi controller site."""

    @property
    def site_id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def description(self) -> str:
        return self.raw.get('desc', '')

    @property
    def role(self) -> str:
        return self.raw.get('role', '')

    @property
    def hidden_id(self) -> str:
        return self.raw.get('attr_hidden_id', '')

    @property
    def no_delete(self) -> bool:
        return self.raw.get('attr_no_delete', False)


# --- Request classes ---


@dataclass(frozen=True)
class SiteListRequest(ApiRequest):
    """GET /api/self/sites - list all accessible sites."""

    method: str = 'GET'
    path: str = '/api/self/sites'

    def full_path(self, site: str, is_unifi_os: bool) -> str:
        """Sites endpoint is global, not scoped to a site."""
        prefix = '/proxy/network' if is_unifi_os else ''
        return f'{prefix}{self.path}'
