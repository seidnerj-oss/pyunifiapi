"""Handler for UniFi port forwards."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.port_forward import PortForward


class PortForwardHandler(APIHandler[PortForward]):
    """Manages the collection of port forwarding rules."""

    item_cls = PortForward
