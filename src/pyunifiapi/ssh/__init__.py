"""SSH-over-WebRTC sessions to UniFi devices."""

__all__ = ['SSHSession']


def __getattr__(name: str):
    if name == 'SSHSession':
        from pyunifiapi.ssh.session import SSHSession

        return SSHSession
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
