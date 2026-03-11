"""Handler for UniFi clients (connected stations)."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.client import Client


class ClientHandler(APIHandler[Client]):
    """Manages the collection of connected clients."""

    item_cls = Client
    id_field = 'mac'
