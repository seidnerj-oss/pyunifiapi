"""Tests for enable_ssh."""

from __future__ import annotations

import shlex
from unittest.mock import patch

import pytest

from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import ControllerConfig, SSHConfig, SSHEnableResult
from pyunifiapi.ssh.dropbear import enable_ssh

SESSION_PATCH = 'pyunifiapi.ssh.dropbear.SSHSession'
PUBLIC_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterial user@host'
PROMPT = 'root@LTEBackupPro:~# '


class FakeDeviceShell:
    """Stands in for SSHSession: interprets the few commands enable_ssh sends."""

    def __init__(self, *, authorized_keys: list[str], running: bool, start_works: bool = True, garble: bool = False) -> None:
        self.authorized_keys = authorized_keys
        self.running = running
        self.start_works = start_works
        self.garble = garble
        self.commands: list[str] = []
        self.ssh_config: SSHConfig | None = None

    def __call__(self, controller: object, ssh: SSHConfig) -> FakeDeviceShell:
        self.ssh_config = ssh
        return self

    async def __aenter__(self) -> FakeDeviceShell:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def read_until(self, marker: str, timeout: float) -> bytes:
        return f'BusyBox banner\n{PROMPT}'.encode()

    async def execute(self, command: str) -> str:
        self.commands.append(command)
        echo = f'{command}\r\n'
        if self.garble:
            return f'{echo}sh: syntax error\r\n{PROMPT}'
        if command.startswith('if '):
            if 'grep -qxF' in command:
                held = shlex.split(command)[3] in self.authorized_keys
            else:
                held = self.running
            return f'{echo}{"PYUNIFIAPI_TRUE" if held else "PYUNIFIAPI_FALSE"}\r\n{PROMPT}'
        if '>> ' in command:
            self.authorized_keys.append(shlex.split(command.split('echo ', 1)[1])[0])
        elif command == 'dropbear -R':
            self.running = self.start_works
        return f'{echo}{PROMPT}'

    def ran(self, fragment: str) -> int:
        return sum(fragment in c for c in self.commands)


@pytest.fixture
def controller_config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password')


async def run(device: FakeDeviceShell, controller: ControllerConfig, public_key: str = PUBLIC_KEY) -> SSHEnableResult:
    with patch(SESSION_PATCH, device):
        return await enable_ssh(controller, 'aa:bb:cc:dd:ee:ff', public_key)


class TestEnableSSH:
    async def test_appends_key_when_absent(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=['ssh-rsa AAAAother other@host'], running=True)

        result = await run(device, controller_config)

        assert result.key_added is True
        assert device.authorized_keys == ['ssh-rsa AAAAother other@host', PUBLIC_KEY]
        assert device.ran('>> /etc/dropbear/authorized_keys') == 1
        assert device.ssh_config == SSHConfig(mac='aa:bb:cc:dd:ee:ff')

    async def test_does_not_duplicate_present_key(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[PUBLIC_KEY], running=True)

        result = await run(device, controller_config)

        assert result.key_added is False
        assert device.authorized_keys == [PUBLIC_KEY]
        assert device.ran('>>') == 0
        assert device.ran('chmod 600 /etc/dropbear/authorized_keys') == 1

    async def test_key_is_stripped_before_matching(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[PUBLIC_KEY], running=True)

        result = await run(device, controller_config, f'  {PUBLIC_KEY}\n')

        assert result.key_added is False
        assert device.authorized_keys == [PUBLIC_KEY]

    async def test_starts_dropbear_when_not_running(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[PUBLIC_KEY], running=False)

        result = await run(device, controller_config)

        assert result == SSHEnableResult(key_added=False, dropbear_started=True)
        assert device.running is True
        assert device.ran('dropbear -R') == 1
        assert device.ran("ps | grep -q '[d]ropbear'") == 2

    async def test_does_not_restart_running_dropbear(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[PUBLIC_KEY], running=True)

        result = await run(device, controller_config)

        assert result.dropbear_started is False
        assert device.ran('dropbear -R') == 0

    async def test_raises_when_dropbear_does_not_start(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[], running=False, start_works=False)

        with pytest.raises(SSHSessionError, match='dropbear is not running on aa:bb:cc:dd:ee:ff'):
            await run(device, controller_config)

        assert device.ran('dropbear -R') == 1

    async def test_raises_on_unrecognized_output(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[], running=False, garble=True)

        with pytest.raises(SSHSessionError, match='Unexpected output'):
            await run(device, controller_config)

        assert device.ran('>>') == 0
        assert device.ran('dropbear -R') == 0

    async def test_command_echo_is_not_mistaken_for_result(self, controller_config: ControllerConfig) -> None:
        device = FakeDeviceShell(authorized_keys=[], running=False)

        await run(device, controller_config)

        tests = [c for c in device.commands if c.startswith('if ')]
        assert tests
        assert all('PYUNIFIAPI_TRUE' not in c and 'PYUNIFIAPI_FALSE' not in c for c in tests)

    async def test_key_is_shell_quoted(self, controller_config: ControllerConfig) -> None:
        key = "ssh-ed25519 AAAAkey it's $(reboot)"
        device = FakeDeviceShell(authorized_keys=[], running=True)

        await run(device, controller_config, key)

        assert device.authorized_keys == [key]
        assert all('$(reboot)' not in c or shlex.quote(key) in c for c in device.commands)

    @pytest.mark.parametrize(
        'bad_key',
        ['not-a-key AAAA', 'ssh-ed25519 AAAA one\nssh-ed25519 AAAA two', 'ssh-ed25519 AAAA\x1b[0m'],
    )
    async def test_rejects_invalid_key_without_connecting(self, controller_config: ControllerConfig, bad_key: str) -> None:
        device = FakeDeviceShell(authorized_keys=[], running=False)

        with pytest.raises(ValueError):
            await run(device, controller_config, bad_key)

        assert device.ssh_config is None
        assert device.commands == []
