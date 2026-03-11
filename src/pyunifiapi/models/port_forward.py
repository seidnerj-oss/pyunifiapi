"""Port forwarding model with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


@final
class PortForward(ApiItem):
    """A port forwarding rule."""

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
    def destination_port(self) -> str:
        return self.raw.get('dst_port', '')

    @property
    def forward_ip(self) -> str:
        return self.raw.get('fwd', '')

    @property
    def forward_port(self) -> str:
        return self.raw.get('fwd_port', '')

    @property
    def protocol(self) -> str:
        return self.raw.get('proto', '')

    @property
    def source(self) -> str:
        return self.raw.get('src', '')

    @property
    def port_forward_interface(self) -> str:
        return self.raw.get('pfwd_interface', '')


# --- Request classes ---


@dataclass(frozen=True)
class PortForwardListRequest(ApiRequest):
    """GET /api/s/{site}/rest/portforward - list port forwards."""

    method: str = 'GET'
    path: str = '/api/s/{site}/rest/portforward'


@dataclass(frozen=True)
class PortForwardEnableRequest(ApiRequest):
    """PUT /api/s/{site}/rest/portforward/{id} - enable or disable a port forward."""

    method: str = 'PUT'
    path: str = '/api/s/{site}/rest/portforward/{fwd_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, port_forward: PortForward, enabled: bool) -> PortForwardEnableRequest:
        path = f'/api/s/{{site}}/rest/portforward/{port_forward.id}'
        return cls(path=path, data={'enabled': enabled})
