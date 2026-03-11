"""CLI entry point: python -m pyunifiapi."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from pyunifiapi._types import ControllerConfig, SSHConfig
from pyunifiapi.ssh.session import SSHSession


async def ssh_command(args: argparse.Namespace) -> None:
    """Run an interactive or one-shot SSH session."""
    controller = ControllerConfig(
        host=args.host,
        username=args.username,
        password=args.password,
        port=args.port,
        site=args.site,
        totp_secret=args.totp_secret,
    )
    ssh_config = SSHConfig(
        mac=args.mac,
        username=args.ssh_username,
        password=args.ssh_password,
    )

    async with SSHSession(controller, ssh_config) as ssh:
        if args.command:
            # One-shot: execute command and print output
            output = await ssh.execute(args.command, prompt=args.prompt)
            print(output)
        else:
            # Interactive mode: pipe stdin/stdout
            print(f'Connected to {args.mac}. Type commands (Ctrl+C to exit).')

            async def read_loop() -> None:
                try:
                    while ssh.connected:
                        data = await ssh.read(timeout=0.5)
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                except TimeoutError:
                    pass
                except Exception:
                    pass

            read_task = asyncio.create_task(read_loop())
            try:
                loop = asyncio.get_event_loop()
                while ssh.connected:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    if not line:
                        break
                    await ssh.write(line)
            except (KeyboardInterrupt, EOFError):
                pass
            finally:
                read_task.cancel()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='pyunifiapi',
        description='Python client for UniFi Network controller and cloud API over WebRTC',
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug logging')
    subparsers = parser.add_subparsers(dest='command_name')

    # SSH subcommand
    ssh_parser = subparsers.add_parser('ssh', help='SSH to a UniFi device via WebRTC')
    ssh_parser.add_argument('--host', required=True, help='Controller hostname or IP')
    ssh_parser.add_argument('--username', required=True, help='Controller username')
    ssh_parser.add_argument('--password', required=True, help='Controller password')
    ssh_parser.add_argument('--mac', required=True, help='Target device MAC address')
    ssh_parser.add_argument('--port', type=int, default=443, help='Controller port (default: 443)')
    ssh_parser.add_argument('--site', default='default', help='UniFi site (default: default)')
    ssh_parser.add_argument('--totp-secret', help='TOTP secret (base32) for 2FA-enabled controllers')
    ssh_parser.add_argument('--ssh-username', default='ubnt', help='SSH username on device (default: ubnt)')
    ssh_parser.add_argument('--ssh-password', default='ubnt', help='SSH password on device (default: ubnt)')
    ssh_parser.add_argument('--command', '-c', help='Execute a single command and exit')
    ssh_parser.add_argument('--prompt', default='# ', help='Shell prompt for command detection (default: "# ")')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(name)s %(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    if args.command_name == 'ssh':
        asyncio.run(ssh_command(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
