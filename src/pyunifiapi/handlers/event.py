"""Handler for UniFi controller events."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.event import Event


class EventHandler(APIHandler[Event]):
    """Manages the collection of controller events."""

    item_cls = Event
