# pyunifiapi

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
pip install pyunifiapi
```

Or with uv:

```bash
uv add pyunifiapi
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

### Enable direct SSH on a device

Some devices (e.g. the LTE Backup Pro) come back from a reboot with their dropbear SSH server stopped. `enable_ssh` opens the debug terminal, appends your public key to `/etc/dropbear/authorized_keys` unless that exact line is already there, starts `dropbear -R` unless it is already running, and raises `SSHSessionError` if dropbear is still not running afterwards:

```python
from pathlib import Path
from pyunifiapi import enable_ssh

result = await enable_ssh(controller, 'aa:bb:cc:dd:ee:ff', Path('~/.ssh/id_ed25519.pub').expanduser().read_text())
print(result.key_added, result.dropbear_started)
```

`controller` is a `ControllerConfig` or `CloudConfig`. dropbear does not survive a reboot on such devices, so run it again after one; repeated calls are safe.

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

- [node-unifiapi](https://github.com/delian/node-unifiapi) - Node.js client whose protocol work served as a reference; pyunifiapi is an independent implementation
- [aiounifi](https://github.com/Kane610/aiounifi) - Async UniFi controller library for Home Assistant (REST API only, no SSH)
- [red-alert](https://github.com/seidnerj/red-alert) - Israeli Home Front Command alert monitor (uses this for UniFi LTE Pro SSH setup)

## Disclaimer and Legal Notice

Ubiquiti, UniFi and UniFi OS are trademarks of Ubiquiti Inc. This project is not affiliated with, endorsed by, or sponsored by Ubiquiti Inc.

This library talks to the UniFi Network controller REST API and to Ubiquiti's cloud signaling and WebRTC endpoints, several of which are undocumented and can change without notice. Use of Ubiquiti's cloud services is governed by Ubiquiti's [Terms of Service](https://ui.com/legal/termsofservice/); automated or unofficial access may conflict with them, and Ubiquiti may block it or suspend the associated UI account. **You assume all risk of using this library, including the risk of losing access to your UI account.**

Use it only against controllers and devices you own or are authorized to administer.

## License

MIT © 2026 seidnerj

This software is provided "as is" without warranty of any kind. See [LICENSE](LICENSE) for full terms.
