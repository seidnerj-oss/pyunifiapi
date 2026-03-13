# py-unifiapi

Python client for UniFi Network controller and cloud API over WebRTC.

Provides programmatic access to UniFi devices - REST API, SSH sessions via the controller's WebRTC debug terminal protocol, and cloud API proxied over WebRTC data channels. Supports TOTP-based 2FA.

## Features

- **Local REST API** - Full UniFi controller REST API client (devices, clients, networks, statistics, settings)
- **SSH-over-WebRTC** - Open SSH sessions to UniFi devices through the controller, using the same WebRTC protocol as the browser debug terminal
- **Cloud API** - Connect to cloud-managed controllers via Ubiquiti SSO and WebRTC data channels
- **2FA support** - TOTP-based two-factor authentication for controllers and cloud SSO
- **Async-first** - Built on asyncio with httpx, aiortc, and websockets

## Installation

```bash
pip install py-unifiapi
```

Or with uv:

```bash
uv add py-unifiapi
```

## Quick Start

### SSH to a device

```python
import asyncio
from pyunifiapi import ControllerConfig, SSHConfig, SSHSession

async def main():
    controller = ControllerConfig(
        host='192.168.1.1',
        username='admin',
        password='your-password',
    )
    ssh = SSHConfig(mac='aa:bb:cc:dd:ee:ff')

    async with SSHSession(controller, ssh) as session:
        output = await session.execute('uptime')
        print(output)

asyncio.run(main())
```

### REST API client

```python
import asyncio
from pyunifiapi import ControllerConfig, UnifiClient

async def main():
    config = ControllerConfig(
        host='192.168.1.1',
        username='admin',
        password='your-password',
    )

    async with UnifiClient(config) as client:
        devices = await client.list_devices()
        for device in devices:
            print(f"{device['name']} ({device['mac']})")

        clients = await client.list_clients()
        print(f'{len(clients)} active clients')

asyncio.run(main())
```

### CLI

```bash
# Interactive SSH session
pyunifiapi ssh --host 192.168.1.1 --username admin --password secret --mac aa:bb:cc:dd:ee:ff

# Execute a single command
pyunifiapi ssh --host 192.168.1.1 --username admin --password secret --mac aa:bb:cc:dd:ee:ff -c "uptime"
```

## How SSH-over-WebRTC Works

The UniFi controller's browser debug terminal uses WebRTC data channels for SSH access. This library implements the same protocol:

1. Authenticate with the controller REST API
2. Request STUN/TURN credentials from the controller
3. Tell the controller to initiate an SSH session on the target device
4. Poll for the device's SDP offer (the device generates a WebRTC offer)
5. Create a WebRTC peer connection, accept the offer, and generate an answer
6. Send the SDP answer back through the controller
7. Wait for the device to open a WebRTC data channel
8. Read/write terminal I/O over the data channel

This means SSH works even if you can't directly reach the device's SSH port - the WebRTC ICE/STUN/TURN mechanism handles NAT traversal.

## Requirements

- Python 3.14+
- A UniFi controller (tested with UniFi Network Application 8.x)
- For SSH: the target device must support the WebRTC debug terminal (most UniFi devices do)

## Development

```bash
uv sync --group dev
uv run pytest tests/ -v
```

## Related Projects

- [node-unifiapi](https://github.com/delian/node-unifiapi) - The original Node.js implementation
- [aiounifi](https://github.com/Kane610/aiounifi) - Async UniFi controller library for Home Assistant (REST API only, no SSH)
- [red-alert](https://github.com/seidnerj/red-alert) - Israeli Home Front Command alert monitor (uses this for UniFi LTE Pro SSH setup)

## License

MIT
