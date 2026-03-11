"""Handlers for UniFi DPI restriction apps and groups."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.dpi import DPIRestrictionApp, DPIRestrictionGroup


class DPIRestrictionAppHandler(APIHandler[DPIRestrictionApp]):
    """Manages the collection of DPI restriction apps."""

    item_cls = DPIRestrictionApp


class DPIRestrictionGroupHandler(APIHandler[DPIRestrictionGroup]):
    """Manages the collection of DPI restriction groups."""

    item_cls = DPIRestrictionGroup
