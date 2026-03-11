"""Handlers for UniFi firewall zones and policies."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.firewall import FirewallPolicy, FirewallZone


class FirewallZoneHandler(APIHandler[FirewallZone]):
    """Manages the collection of firewall zones."""

    item_cls = FirewallZone


class FirewallPolicyHandler(APIHandler[FirewallPolicy]):
    """Manages the collection of firewall policies."""

    item_cls = FirewallPolicy
