"""Handler for UniFi traffic routes."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.traffic_route import TrafficRoute


class TrafficRouteHandler(APIHandler[TrafficRoute]):
    """Manages the collection of traffic routes."""

    item_cls = TrafficRoute
