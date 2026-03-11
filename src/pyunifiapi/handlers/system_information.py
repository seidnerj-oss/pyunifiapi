"""Handler for UniFi system information."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.system_information import SystemInformation


class SystemInformationHandler(APIHandler[SystemInformation]):
    """Manages system information entries."""

    item_cls = SystemInformation
    id_field = 'anonymous_controller_id'
