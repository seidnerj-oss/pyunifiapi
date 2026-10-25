"""SSH-over-WebRTC sessions to UniFi devices."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Re-exported for static analysis only; resolved lazily at runtime below.
    from pyunifiapi.ssh.dropbear import enable_ssh
    from pyunifiapi.ssh.session import SSHSession

__all__ = ['SSHSession', 'enable_ssh']


def __getattr__(name: str):
    if name == 'SSHSession':
        from pyunifiapi.ssh.session import SSHSession

        return SSHSession
    if name == 'enable_ssh':
        from pyunifiapi.ssh.dropbear import enable_ssh

        return enable_ssh
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
