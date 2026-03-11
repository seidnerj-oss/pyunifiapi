"""Handler for UniFi sites."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.site import Site


class SiteHandler(APIHandler[Site]):
    """Manages the collection of controller sites."""

    item_cls = Site
