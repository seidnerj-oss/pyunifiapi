"""Voucher (hotspot guest pass) model with typed properties."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, final

from pyunifiapi.models.api import ApiItem, ApiRequest


class VoucherStatus(StrEnum):
    """Voucher validity status."""

    VALID_ONE = 'VALID_ONE'
    VALID_MULTI = 'VALID_MULTI'
    USED_MULTIPLE = 'USED_MULTIPLE'


@final
class Voucher(ApiItem):
    """A hotspot guest voucher."""

    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def site_id(self) -> str:
        return self.raw.get('site_id', '')

    @property
    def code(self) -> str:
        """Formatted voucher code (e.g. 'XXXXX-XXXXX')."""
        raw_code = self.raw.get('code', '')
        if len(raw_code) == 10:
            return f'{raw_code[:5]}-{raw_code[5:]}'
        return raw_code

    @property
    def admin_name(self) -> str:
        return self.raw.get('admin_name', '')

    @property
    def note(self) -> str:
        return self.raw.get('note', '')

    @property
    def quota(self) -> int:
        """Usage limit: 0 = unlimited."""
        return self.raw.get('quota', 0)

    @property
    def used(self) -> int:
        return self.raw.get('used', 0)

    @property
    def duration(self) -> int:
        """Duration in minutes."""
        return self.raw.get('duration', 0)

    @property
    def for_hotspot(self) -> bool:
        return self.raw.get('for_hotspot', False)

    @property
    def create_time(self) -> int:
        """Unix timestamp when voucher was created."""
        return self.raw.get('create_time', 0)

    @property
    def start_time(self) -> int:
        """Unix timestamp when voucher was first used (0 if not used)."""
        return self.raw.get('start_time', 0)

    @property
    def end_time(self) -> int:
        """Unix timestamp when voucher expires (0 if not used)."""
        return self.raw.get('end_time', 0)

    @property
    def qos_overwrite(self) -> bool:
        return self.raw.get('qos_overwrite', False)

    @property
    def qos_usage_quota(self) -> int:
        """Data usage quota in MB."""
        return self.raw.get('qos_usage_quota', 0)

    @property
    def qos_rate_max_up(self) -> int:
        """Max upload rate in kbps."""
        return self.raw.get('qos_rate_max_up', 0)

    @property
    def qos_rate_max_down(self) -> int:
        """Max download rate in kbps."""
        return self.raw.get('qos_rate_max_down', 0)

    @property
    def status(self) -> str:
        return self.raw.get('status', '')


# --- Request classes ---


@dataclass(frozen=True)
class VoucherListRequest(ApiRequest):
    """GET /api/s/{site}/stat/voucher - list vouchers."""

    method: str = 'GET'
    path: str = '/api/s/{site}/stat/voucher'


@dataclass(frozen=True)
class VoucherCreateRequest(ApiRequest):
    """POST /api/s/{site}/cmd/hotspot - create vouchers."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/hotspot'
    data: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        expire_number: int,
        expire_unit: int = 1,
        number: int = 1,
        quota: int = 0,
        usage_quota: int | None = None,
        rate_max_up: int | None = None,
        rate_max_down: int | None = None,
        note: str | None = None,
    ) -> VoucherCreateRequest:
        """Create a voucher creation request.

        Args:
            expire_number: Expiration number (combined with expire_unit).
            expire_unit: 1=minute, 60=hour, 1440=day.
            number: How many vouchers to create.
            quota: Usage count limit (0=unlimited).
            usage_quota: Data quota in MB.
            rate_max_up: Max upload rate in kbps.
            rate_max_down: Max download rate in kbps.
            note: Optional note.
        """
        payload: dict[str, Any] = {
            'cmd': 'create-voucher',
            'expire': expire_number,
            'expire_unit': expire_unit,
            'n': number,
            'quota': quota,
        }
        if usage_quota is not None:
            payload['bytes'] = usage_quota
        if rate_max_up is not None:
            payload['up'] = rate_max_up
        if rate_max_down is not None:
            payload['down'] = rate_max_down
        if note is not None:
            payload['note'] = note
        return cls(data=payload)


@dataclass(frozen=True)
class VoucherDeleteRequest(ApiRequest):
    """POST /api/s/{site}/cmd/hotspot - delete a voucher."""

    method: str = 'POST'
    path: str = '/api/s/{site}/cmd/hotspot'
    data: dict[str, Any] | None = None

    @classmethod
    def create(cls, voucher_id: str) -> VoucherDeleteRequest:
        return cls(data={'cmd': 'delete-voucher', '_id': voucher_id})
