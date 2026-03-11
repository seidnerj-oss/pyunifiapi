"""Shared data types for py-unifiapi."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyunifiapi._constants import DEFAULT_CONTROLLER_PORT, DEFAULT_SITE, DEFAULT_SSH_PASSWORD, DEFAULT_SSH_USERNAME


@dataclass(frozen=True)
class ControllerConfig:
    """Configuration for connecting to a local UniFi controller."""

    host: str
    username: str
    password: str
    port: int = DEFAULT_CONTROLLER_PORT
    site: str = DEFAULT_SITE
    ssl_verify: bool = False
    totp_secret: str | None = None


@dataclass(frozen=True)
class CloudConfig:
    """Configuration for connecting via Ubiquiti cloud."""

    username: str
    password: str
    device_id: str
    totp_secret: str | None = None


@dataclass(frozen=True)
class SSHConfig:
    """Configuration for an SSH session to a UniFi device."""

    mac: str
    username: str = DEFAULT_SSH_USERNAME
    password: str = DEFAULT_SSH_PASSWORD


@dataclass(frozen=True)
class TurnCredentials:
    """STUN/TURN server credentials for WebRTC."""

    stun_urls: list[str] = field(default_factory=list)
    turn_urls: list[str] = field(default_factory=list)
    turn_username: str = ''
    turn_password: str = ''


@dataclass(frozen=True)
class SDPExchange:
    """SDP offer/answer pair for WebRTC signaling."""

    uuid: str
    offer: str
    answer: str | None = None
