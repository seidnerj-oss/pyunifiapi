"""Traffic rule model with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequestV2


@final
class TrafficRule(ApiItem):
    """A traffic management rule."""

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
    def action(self) -> str:
        """Rule action: 'BLOCK', 'ALLOW', or 'RATE_LIMIT'."""
        return self.raw.get('action', '')

    @property
    def matching_target(self) -> str:
        """What to match: 'DOMAIN', 'IP', 'INTERNET', 'REGION'."""
        return self.raw.get('matching_target', '')

    @property
    def target_devices(self) -> list[dict[str, Any]]:
        return self.raw.get('target_devices', [])

    @property
    def app_ids(self) -> list[int]:
        return self.raw.get('app_ids', [])

    @property
    def app_category_ids(self) -> list[int]:
        return self.raw.get('app_category_ids', [])

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
    def network_ids(self) -> list[str]:
        return self.raw.get('network_ids', [])

    @property
    def bandwidth_limit(self) -> dict[str, Any]:
        return self.raw.get('bandwidth_limit', {})

    @property
    def schedule(self) -> dict[str, Any]:
        return self.raw.get('schedule', {})


# --- Request classes ---


@dataclass(frozen=True)
class TrafficRuleListRequest(ApiRequestV2):
    """GET /v2/api/site/{site}/trafficrules - list traffic rules."""

    method: str = 'GET'
    path: str = '/trafficrules'


@dataclass(frozen=True)
class TrafficRuleEnableRequest(ApiRequestV2):
    """PUT /v2/api/site/{site}/trafficrules/{id} - enable or disable a traffic rule."""

    method: str = 'PUT'
    path: str = '/trafficrules/{rule_id}'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, rule: TrafficRule, enabled: bool) -> TrafficRuleEnableRequest:
        path = f'/trafficrules/{rule.id}'
        return cls(path=path, data={**rule.raw, 'enabled': enabled})
