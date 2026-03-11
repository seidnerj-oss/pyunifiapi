"""Traffic route model with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequestV2


class MatchingTarget(StrEnum):
    """Traffic route matching target types."""

    DOMAIN = 'DOMAIN'
    IP = 'IP'
    INTERNET = 'INTERNET'
    REGION = 'REGION'


@final
class TrafficRoute(ApiItem):
    """A traffic routing rule."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def description(self) -> str:
        return self.raw.get('description', '')

    @property
    def enabled(self) -> bool:
        return self.raw.get('enabled', False)

    @property
    def matching_target(self) -> str:
        return self.raw.get('matching_target', '')

    @property
    def network_id(self) -> str:
        return self.raw.get('network_id', '')

    @property
    def next_hop(self) -> str:
        return self.raw.get('next_hop', '')

    @property
    def domains(self) -> list[dict[str, Any]]:
        return self.raw.get('domains', [])

    @property
    def ip_addresses(self) -> list[dict[str, Any]]:
        return self.raw.get('ip_addresses', [])

    @property
    def ip_ranges(self) -> list[dict[str, Any]]:
        return self.raw.get('ip_ranges', [])

    @property
    def regions(self) -> list[str]:
        return self.raw.get('regions', [])

    @property
    def target_devices(self) -> list[dict[str, Any]]:
        return self.raw.get('target_devices', [])


# --- Request classes ---


@dataclass(frozen=True)
class TrafficRouteListRequest(ApiRequestV2):
    """GET /v2/api/site/{site}/trafficroutes - list traffic routes."""

    method: str = 'GET'
    path: str = '/trafficroutes'


@dataclass(frozen=True)
class TrafficRouteSaveRequest(ApiRequestV2):
    """PUT /v2/api/site/{site}/trafficroutes/{id} - update a traffic route."""

    method: str = 'PUT'
    path: str = '/trafficroutes/{route_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, route: TrafficRoute, enabled: bool | None = None) -> TrafficRouteSaveRequest:
        payload = dict(route.raw)
        if enabled is not None:
            payload['enabled'] = enabled
        path = f'/trafficroutes/{route.id}'
        return cls(path=path, data=payload)
