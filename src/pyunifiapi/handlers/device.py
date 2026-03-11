"""Handler for UniFi devices."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.device import Device


class DeviceHandler(APIHandler[Device]):
    """Manages the collection of UniFi devices (APs, switches, gateways, etc.)."""

    item_cls = Device
    id_field = 'mac'
