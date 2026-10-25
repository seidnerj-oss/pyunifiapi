"""Enable the dropbear SSH server on a UniFi device through its debug terminal.

Some UniFi devices (e.g. the LTE Backup Pro) come back from a reboot with
dropbear stopped, so direct SSH is refused until it is started again. This
opens the controller's WebRTC debug terminal (:class:`SSHSession`), authorizes
a public key and starts dropbear, doing nothing that is already done.
"""

from __future__ import annotations

import logging
import shlex

from pyunifiapi._constants import DROPBEAR_AUTHORIZED_KEYS, SSH_BANNER_TIMEOUT
from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import CloudConfig, ControllerConfig, SSHConfig, SSHEnableResult
from pyunifiapi.ssh.session import SSHSession

logger = logging.getLogger(__name__)

PUBLIC_KEY_PREFIXES = ('ssh-', 'ecdsa-', 'sk-')

# Markers are echoed as two adjacent quoted halves, so the terminal's echo of
# the command line never contains the joined marker that the output does.
_TRUE_MARKER = 'PYUNIFIAPI_TRUE'
_FALSE_MARKER = 'PYUNIFIAPI_FALSE'


def _split_echo(marker: str) -> str:
    head, tail = marker.split('_', 1)
    return f"echo '{head}_''{tail}'"


async def _shell_test(ssh: SSHSession, condition: str) -> bool:
    """Run a shell condition on the device and return whether it held."""
    output = await ssh.execute(f'if {condition}; then {_split_echo(_TRUE_MARKER)}; else {_split_echo(_FALSE_MARKER)}; fi')
    if _TRUE_MARKER in output:
        return True
    if _FALSE_MARKER in output:
        return False
    raise SSHSessionError(f'Unexpected output while testing {condition!r}: {output!r}')


def _validate_public_key(public_key: str) -> str:
    key = public_key.strip()
    if not key.startswith(PUBLIC_KEY_PREFIXES):
        raise ValueError(f'Does not look like an SSH public key: {key[:40]!r}')
    if any(ch in key for ch in '\r\n') or not key.isprintable():
        raise ValueError('SSH public key must be a single printable line')
    return key


async def enable_ssh(
    controller: ControllerConfig | CloudConfig,
    device_mac: str,
    public_key: str,
) -> SSHEnableResult:
    """Authorize ``public_key`` on a device and make sure dropbear is running.

    Connects through the controller's WebRTC debug terminal, appends the key to
    ``/etc/dropbear/authorized_keys`` unless that exact line is already there,
    starts ``dropbear -R`` unless it is already running, then checks that it is.

    Args:
        controller: Local (ControllerConfig) or cloud (CloudConfig) controller connection.
        device_mac: MAC address of the target device.
        public_key: One OpenSSH public key line (``ssh-ed25519 AAAA... comment``).

    Returns:
        Which of the two steps actually changed something on the device.

    Raises:
        ValueError: ``public_key`` is not a single OpenSSH public key line.
        SSHSessionError: dropbear is still not running after starting it, or the
            device returned output that could not be interpreted.
    """
    key = _validate_public_key(public_key)
    quoted_key = shlex.quote(key)
    quoted_path = shlex.quote(DROPBEAR_AUTHORIZED_KEYS)

    async with SSHSession(controller, SSHConfig(mac=device_mac)) as ssh:
        logger.info('Connected to device %s via WebRTC debug terminal', device_mac)
        await ssh.read_until('# ', timeout=SSH_BANNER_TIMEOUT)

        key_added = not await _shell_test(ssh, f'grep -qxF {quoted_key} {quoted_path} 2>/dev/null')
        if key_added:
            await ssh.execute(f'mkdir -p "$(dirname {quoted_path})" && echo {quoted_key} >> {quoted_path}')
            logger.info('Public key appended to %s', DROPBEAR_AUTHORIZED_KEYS)
        await ssh.execute(f'chmod 600 {quoted_path}')

        is_running = "ps | grep -q '[d]ropbear'"
        dropbear_started = not await _shell_test(ssh, is_running)
        if dropbear_started:
            await ssh.execute('dropbear -R')
            if not await _shell_test(ssh, is_running):
                raise SSHSessionError(f'dropbear is not running on {device_mac} after starting it')
            logger.info('dropbear started on %s', device_mac)

    return SSHEnableResult(key_added=key_added, dropbear_started=dropbear_started)
