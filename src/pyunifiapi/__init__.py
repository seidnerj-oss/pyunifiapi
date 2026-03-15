"""pyunifiapi - Python client for UniFi Network controller and cloud API over WebRTC."""

from pyunifiapi._exceptions import (
    ApiConnectionError,
    AuthenticationError,
    LoginRequired,
    PyUnifiApiError,
    RequestError,
    SDPPollTimeoutError,
    SignalingError,
    SSHSessionError,
    WebRTCError,
    WebSocketError,
)
from pyunifiapi._types import CloudConfig, ControllerConfig, SSHConfig, TurnCredentials
from pyunifiapi.client import UnifiClient
from pyunifiapi.controller import Controller


def __getattr__(name: str):
    """Lazy imports for cloud/WebRTC modules that require optional dependencies."""
    if name == 'CloudClient':
        from pyunifiapi.cloud import CloudClient

        return CloudClient
    if name == 'CloudController':
        from pyunifiapi.cloud_controller import CloudController

        return CloudController
    if name == 'SSHSession':
        from pyunifiapi.ssh.session import SSHSession

        return SSHSession
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = [
    'ApiConnectionError',
    'AuthenticationError',
    'CloudClient',
    'CloudConfig',
    'CloudController',
    'Controller',
    'ControllerConfig',
    'LoginRequired',
    'PyUnifiApiError',
    'RequestError',
    'SDPPollTimeoutError',
    'SSHConfig',
    'SSHSession',
    'SignalingError',
    'SSHSessionError',
    'TurnCredentials',
    'UnifiClient',
    'WebRTCError',
    'WebSocketError',
]
