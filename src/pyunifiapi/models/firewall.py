"""Firewall zone and policy models with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequestV2


@final
class FirewallZone(ApiItem):
    """A firewall zone grouping network interfaces."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def zone_key(self) -> str:
        return self.raw.get('zone_key', '')

    @property
    def default_zone(self) -> bool:
        return self.raw.get('default_zone', False)

    @property
    def no_edit(self) -> bool:
        return self.raw.get('attr_no_edit', False)

    @property
    def network_ids(self) -> list[str]:
        return self.raw.get('network_ids', [])


@final
class FirewallPolicy(ApiItem):
    """A firewall policy rule."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')

    @property
    def enabled(self) -> bool:
        return self.raw.get('enabled', False)

    @property
    def action(self) -> str:
        """Policy action: 'ACCEPT', 'DROP', 'REJECT'."""
        return self.raw.get('action', '')

    @property
    def protocol(self) -> str:
        return self.raw.get('protocol', '')

    @property
    def protocol_match_excepted(self) -> bool:
        return self.raw.get('protocol_match_excepted', False)

    @property
    def ip_version(self) -> str:
        return self.raw.get('ip_version', '')

    @property
    def logging(self) -> bool:
        return self.raw.get('logging', False)

    @property
    def index(self) -> int:
        return self.raw.get('index', 0)

    @property
    def source(self) -> dict[str, Any]:
        return self.raw.get('source', {})

    @property
    def destination(self) -> dict[str, Any]:
        return self.raw.get('destination', {})

    @property
    def connection_state_type(self) -> str:
        return self.raw.get('connection_state_type', '')

    @property
    def connection_states(self) -> list[str]:
        return self.raw.get('connection_states', [])

    @property
    def icmp_typename(self) -> str:
        return self.raw.get('icmp_typename', '')

    @property
    def icmp_v6_typename(self) -> str:
        return self.raw.get('icmp_v6_typename', '')

    @property
    def match_ipsec(self) -> str:
        return self.raw.get('match_ipsec', '')

    @property
    def schedule(self) -> dict[str, Any]:
        return self.raw.get('schedule', {})


# --- Request classes ---


@dataclass(frozen=True)
class FirewallZoneListRequest(ApiRequestV2):
    """GET /v2/api/site/{site}/firewall/zone - list firewall zones."""

    method: str = 'GET'
    path: str = '/firewall/zone'


@dataclass(frozen=True)
class FirewallZoneUpdateRequest(ApiRequestV2):
    """PUT /v2/api/site/{site}/firewall/zone/{id} - update a firewall zone."""

    method: str = 'PUT'
    path: str = '/firewall/zone/{zone_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, zone: FirewallZone) -> FirewallZoneUpdateRequest:
        path = f'/firewall/zone/{zone.id}'
        return cls(path=path, data=dict(zone.raw))


@dataclass(frozen=True)
class FirewallPolicyListRequest(ApiRequestV2):
    """GET /v2/api/site/{site}/firewall-policies - list firewall policies."""

    method: str = 'GET'
    path: str = '/firewall-policies'


@dataclass(frozen=True)
class FirewallPolicyUpdateRequest(ApiRequestV2):
    """PUT /v2/api/site/{site}/firewall-policies/{id} - update a firewall policy."""

    method: str = 'PUT'
    path: str = '/firewall-policies/{policy_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, policy: FirewallPolicy) -> FirewallPolicyUpdateRequest:
        path = f'/firewall-policies/{policy.id}'
        return cls(path=path, data=dict(policy.raw))
