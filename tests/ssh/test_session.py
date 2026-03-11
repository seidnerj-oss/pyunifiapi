"""Tests for SSHSession."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import ControllerConfig, SSHConfig, TurnCredentials
from pyunifiapi.ssh.session import SSHSession


@pytest.fixture
def controller_config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password')


@pytest.fixture
def ssh_config() -> SSHConfig:
    return SSHConfig(mac='aa:bb:cc:dd:ee:ff')


class TestSSHSession:
    async def test_connect_flow(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        """Test the full connect orchestration calls the right methods in order."""
        session = SSHSession(controller_config, ssh_config)

        turn = TurnCredentials(
            stun_urls=['stun:stun.example.com:3478'],
            turn_urls=['turn:turn.example.com:3478'],
            turn_username='user',
            turn_password='pass',
        )

        mock_http = AsyncMock()
        mock_signaling = AsyncMock()
        mock_signaling.get_turn_credentials.return_value = turn
        mock_signaling.poll_sdp_offer.return_value = 'v=0\r\nfake-offer'

        mock_channel = MagicMock()
        mock_channel.readyState = 'open'
        mock_channel.on = MagicMock()

        mock_peer = AsyncMock()
        mock_peer.accept_offer.return_value = 'v=0\r\nfake-answer'
        mock_peer.wait_for_channel.return_value = mock_channel
        mock_peer.message_queue = asyncio.Queue()

        with (
            patch('pyunifiapi.ssh.session.LocalHttpTransport', return_value=mock_http),
            patch('pyunifiapi.ssh.session.LocalSignaling', return_value=mock_signaling),
            patch('pyunifiapi.ssh.session.PeerConnection', return_value=mock_peer),
        ):
            await session.connect()

            assert session.connected is True
            mock_http.login.assert_called_once()
            mock_signaling.get_turn_credentials.assert_called_once()
            mock_signaling.build_ssh_session.assert_called_once()
            mock_signaling.poll_sdp_offer.assert_called_once()
            mock_peer.accept_offer.assert_called_once_with('v=0\r\nfake-offer')
            mock_signaling.send_sdp_answer.assert_called_once()

    async def test_write_not_connected(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        session = SSHSession(controller_config, ssh_config)

        with pytest.raises(SSHSessionError, match='not connected'):
            await session.write('test')

    async def test_read_not_connected(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        session = SSHSession(controller_config, ssh_config)

        with pytest.raises(SSHSessionError, match='not connected'):
            await session.read()

    async def test_close_cleans_up(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        session = SSHSession(controller_config, ssh_config)

        mock_signaling = AsyncMock()
        mock_peer = AsyncMock()
        mock_http = AsyncMock()

        session._signaling = mock_signaling
        session._peer = mock_peer
        session._http = mock_http
        session._uuid = 'test-uuid'
        session._connected = True

        await session.close()

        assert session.connected is False
        mock_signaling.close_ssh_session.assert_called_once()
        mock_peer.close.assert_called_once()
        mock_http.close.assert_called_once()

    async def test_close_handles_signaling_error(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        """Close should not raise even if signaling cleanup fails."""
        session = SSHSession(controller_config, ssh_config)

        mock_signaling = AsyncMock()
        mock_signaling.close_ssh_session.side_effect = Exception('network error')
        mock_peer = AsyncMock()
        mock_http = AsyncMock()

        session._signaling = mock_signaling
        session._peer = mock_peer
        session._http = mock_http
        session._uuid = 'test-uuid'
        session._connected = True

        # Should not raise
        await session.close()
        assert session.connected is False

    async def test_context_manager(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        session = SSHSession(controller_config, ssh_config)

        with (
            patch.object(session, 'connect', new_callable=AsyncMock) as mock_connect,
            patch.object(session, 'close', new_callable=AsyncMock) as mock_close,
        ):
            async with session as s:
                assert s is session
                mock_connect.assert_called_once()

            mock_close.assert_called_once()
