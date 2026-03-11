"""Exception hierarchy for py-unifiapi."""


class PyUnifiApiError(Exception):
    """Base exception for all py-unifiapi errors."""


class AuthenticationError(PyUnifiApiError):
    """Login failed (bad credentials, 2FA required, etc.)."""


class ApiConnectionError(PyUnifiApiError):
    """Cannot reach controller or cloud endpoint."""


class SignalingError(PyUnifiApiError):
    """SDP exchange or ICE negotiation failed."""


class WebRTCError(PyUnifiApiError):
    """WebRTC peer connection or data channel error."""


class SSHSessionError(PyUnifiApiError):
    """SSH session setup or communication error."""


class SDPPollTimeoutError(PyUnifiApiError):
    """Timed out waiting for SDP offer from device."""


class WebSocketError(PyUnifiApiError):
    """WebSocket connection or communication error."""


class LoginRequired(PyUnifiApiError):
    """Operation requires an active authenticated session."""


class RequestError(PyUnifiApiError):
    """API request returned an error response."""
