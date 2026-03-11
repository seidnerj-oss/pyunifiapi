"""Handler for UniFi vouchers."""

from __future__ import annotations

from pyunifiapi.handlers.api import APIHandler
from pyunifiapi.models.voucher import Voucher


class VoucherHandler(APIHandler[Voucher]):
    """Manages the collection of guest vouchers."""

    item_cls = Voucher
