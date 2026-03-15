"""WebRTC peer connection and data channel management."""

__all__ = ['PeerConnection']


def __getattr__(name: str):
    if name == 'PeerConnection':
        from pyunifiapi.webrtc._peer import PeerConnection

        return PeerConnection
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
