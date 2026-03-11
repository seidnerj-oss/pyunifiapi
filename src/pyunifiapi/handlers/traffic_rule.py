"""Handler for UniFi traffic rules."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.traffic_rule import TrafficRule


class TrafficRuleHandler(APIHandler[TrafficRule]):
    """Manages the collection of traffic rules."""

    item_cls = TrafficRule
