"""WebSocket message types and parsing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MessageKey(StrEnum):
    """Known WebSocket message types from the UniFi controller."""

    ALERT = 'alert'
    CLIENT = 'sta:sync'
    CLIENT_REMOVED = 'user:delete'
    DEVICE = 'device:sync'
    DEVICE_ADD = 'device:add'
    DEVICE_UPDATE = 'device:update'
    DPI_APP_ADDED = 'dpiapp:add'
    DPI_APP_UPDATED = 'dpiapp:sync'
    DPI_APP_REMOVED = 'dpiapp:delete'
    DPI_GROUP_ADDED = 'dpigroup:add'
    DPI_GROUP_UPDATED = 'dpigroup:sync'
    DPI_GROUP_REMOVED = 'dpigroup:delete'
    EVENT = 'events'
    FIREWALL_POLICY_ADDED = 'firewall-policy:add'
    FIREWALL_POLICY_UPDATED = 'firewall-policy:sync'
    FIREWALL_POLICY_REMOVED = 'firewall-policy:delete'
    FIREWALL_RULE_ADDED = 'firewall-rule:add'
    FIREWALL_RULE_UPDATED = 'firewall-rule:sync'
    FIREWALL_RULE_REMOVED = 'firewall-rule:delete'
    FIREWALL_ZONE_ADDED = 'firewall-zone:add'
    FIREWALL_ZONE_UPDATED = 'firewall-zone:sync'
    FIREWALL_ZONE_REMOVED = 'firewall-zone:delete'
    NETWORK_CONF_UPDATED = 'networkconf:sync'
    PORT_FORWARD_ADDED = 'portforward:add'
    PORT_FORWARD_UPDATED = 'portforward:sync'
    PORT_FORWARD_DELETED = 'portforward:delete'
    SETTING_UPDATED = 'setting:sync'
    SITE_UPDATED = 'site:sync'
    SPEED_TEST_UPDATE = 'speed-test:update'
    SYSTEM_UPDATE_STATUS = 'fwupdate:sync'
    TRAFFIC_ROUTE_ADDED = 'trafficroute:add'
    TRAFFIC_ROUTE_UPDATED = 'trafficroute:sync'
    TRAFFIC_ROUTE_REMOVED = 'trafficroute:delete'
    TRAFFIC_RULE_ADDED = 'trafficrule:add'
    TRAFFIC_RULE_UPDATED = 'trafficrule:sync'
    TRAFFIC_RULE_REMOVED = 'trafficrule:delete'
    USER_ADDED = 'user:sync'
    VOUCHER_CREATED = 'voucher:add'
    VOUCHER_DELETED = 'voucher:delete'
    WLAN_CONF_UPDATED = 'wlanconf:sync'


@dataclass
class MessageMeta:
    """Metadata from a WebSocket message."""

    rc: str
    message_key: str
    data: dict[str, Any]

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MessageMeta:
        return cls(
            rc=raw.get('rc', ''),
            message_key=raw.get('message', ''),
            data=raw.get('data', {}),
        )


@dataclass
class Message:
    """A parsed WebSocket message from the controller."""

    meta: MessageMeta
    data: list[dict[str, Any]]

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Message:
        meta = MessageMeta.from_raw(raw.get('meta', {}))
        data = raw.get('data', [])
        if isinstance(data, dict):
            data = [data]
        return cls(meta=meta, data=data)
