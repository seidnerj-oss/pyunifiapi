"""Handler for UniFi WLANs."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.wlan import Wlan


class WlanHandler(APIHandler[Wlan]):
    """Manages the collection of WLAN configurations."""

    item_cls = Wlan
