## Project Overview

pyunifiapi is a Python client for UniFi Network controller and cloud API over WebRTC. The primary use case is SSH access to UniFi devices through the controller's WebRTC debug terminal protocol, enabling programmatic shell access to devices that don't expose SSH directly. Also provides a full REST API client and cloud API access via WebRTC data channels. Supports TOTP-based 2FA.

Code provenance: write code independently; never copy license-incompatible or proprietary code, and preserve notices on any compatible reuse.

## Quick Setup

```bash
uv sync --group dev
uv run pre-commit install
uv run pytest
```

Tests use pytest in `tests/`, mirroring the source structure; a bug fix adds a test that reproduces the bug.

## Architecture

```
src/pyunifiapi/
  __init__.py            # Public API exports
  _constants.py          # URLs, timeouts, API paths
  _types.py              # Dataclasses (ControllerConfig, SSHConfig, TurnCredentials, etc.)
  _exceptions.py         # Exception hierarchy
  client.py              # UnifiClient - local controller REST API (~40 methods)
  cloud.py               # CloudClient - REST via WebRTC data channel through cloud
  controller.py          # Controller connection management
  websocket.py           # WebSocket event streaming
  handlers/              # API handler methods
  models/                # Data models
  http/
    _local.py            # LocalHttpTransport - httpx with cookie auth, CSRF, auto-reauth
    _cloud.py            # CloudHttpTransport - httpx for Ubiquiti SSO (sso.ubnt.com)
  webrtc/
    _peer.py             # PeerConnection - aiortc wrapper (accept_offer/create_offer)
    _framing.py          # Binary message framing for cloud API data channel
  signaling/
    _local.py            # LocalSignaling - SDP exchange via controller REST API
    _cloud.py            # CloudSignaling - SDP exchange via cloud WebSocket
  ssh/
    session.py           # SSHSession - SSH-over-WebRTC orchestrator
  cli/
    __main__.py          # CLI entry point (pyunifiapi ssh ...)
```

## Code Style Guidelines

- **Formatting**: Enforced by ruff (line-length=150, single quotes, py313 target)
- **Naming**: Constants in ALL_CAPS, classes in CamelCase, variables/functions in snake_case
- **Import ordering**: ALL imports at the top of the file, never mid-file
  - Standard library first, then third-party, then local modules
- **Type hints**: Use for function parameters and return values

## Key Design Decisions

- **Two WebRTC modes**: SSH mode (device creates offer, we answer) vs Cloud mode (we create offer with 'api' channel)
- **Separate HTTP transports**: Local (cookie auth) vs Cloud (SSO tokens) have different auth flows
- **Signaling layer**: Decoupled from WebRTC - local uses REST API polling, cloud uses WebSocket
- **Binary framing**: Cloud API multiplexes REST requests over a single data channel using a 16-byte header protocol
