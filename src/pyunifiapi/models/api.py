"""Base classes for API models and requests."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any


class ApiItem(ABC):
    """Base class for typed API response items.

    Wraps a raw dict from the controller API and provides typed property
    accessors. Subclasses define @property methods for each field they
    care about, reading from self.raw.
    """

    raw: dict[str, Any]

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    def __repr__(self) -> str:
        cls = type(self).__name__
        id_val = self.raw.get('_id', self.raw.get('mac', ''))
        return f'{cls}({id_val!r})'


@dataclass(frozen=True)
class ApiRequest:
    """A typed REST API request for V1 endpoints.

    Encapsulates the HTTP method, relative path, and optional JSON body.
    The full URL is constructed by full_path() based on the site name
    and whether the controller is running UniFi OS.
    """

    method: str
    path: str
    data: dict[str, Any] | None = None

    def full_path(self, site: str, is_unifi_os: bool) -> str:
        """Build the absolute API path.

        Args:
            site: UniFi site name (e.g. 'default').
            is_unifi_os: True if the controller runs UniFi OS (Dream Machine, etc.).

        Returns:
            Full path string like '/api/s/default/stat/device' or
            '/proxy/network/api/s/default/stat/device'.
        """
        prefix = '/proxy/network' if is_unifi_os else ''
        return f'{prefix}{self.path}'.format(site=site)


@dataclass(frozen=True)
class ApiRequestV2:
    """A typed REST API request for V2 endpoints.

    V2 endpoints use a different URL structure and typically return data
    directly (no 'data' wrapper array).
    """

    method: str
    path: str
    data: dict[str, Any] | None = None

    def full_path(self, site: str, is_unifi_os: bool) -> str:
        """Build the absolute V2 API path."""
        prefix = '/proxy/network' if is_unifi_os else ''
        return f'{prefix}/v2/api/site/{site}{self.path}'


@dataclass
class TypedApiResponse:
    """Parsed API response from the controller."""

    data: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether the response indicates success."""
        return self.meta.get('rc') == 'ok'

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> TypedApiResponse:
        """Parse a raw JSON response dict."""
        return cls(
            data=raw.get('data', []),
            meta=raw.get('meta', {}),
        )
