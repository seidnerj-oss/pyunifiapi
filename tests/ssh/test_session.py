"""Tests for SSHSession."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyunifiapi._exceptions import SSHSessionError
from pyunifiapi._types import CloudConfig, ControllerConfig, SSHConfig, TurnCredentials
from pyunifiapi.ssh.session import SSHSession

# Patch targets: PeerConnection is a module-level import in session.py,
# others are lazy (imported inside methods) and patched at their source modules.
PEER_PATCH = 'pyunifiapi.ssh.session.PeerConnection'
LOCAL_HTTP_PATCH = 'pyunifiapi.http._local.LocalHttpTransport'
LOCAL_WS_SIG_PATCH = 'pyunifiapi.signaling._local_ws.LocalWebSocketSignaling'
CONTROLLER_PATCH = 'pyunifiapi.controller.Controller'
CLOUD_CLIENT_PATCH = 'pyunifiapi.cloud.CloudClient'
CLOUD_SSH_SIG_PATCH = 'pyunifiapi.signaling._cloud_ssh.CloudSSHSignaling'


@pytest.fixture
def controller_config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='password')


@pytest.fixture
def cloud_config() -> CloudConfig:
    return CloudConfig(username='admin', password='password', device_id='DEVICE123:999')


@pytest.fixture
def ssh_config() -> SSHConfig:
    return SSHConfig(mac='aa:bb:cc:dd:ee:ff')


class TestSSHSession:
    async def test_connect_local_flow(self, controller_config: ControllerConfig, ssh_config: SSHConfig) -> None:
        """Test the full local connect orchestration uses WebSocket signaling."""
        session = SSHSession(controller_config, ssh_config)

        turn = TurnCredentials(
            stun_urls=['stun:stun.example.com:3478'],
        )

        mock_http = AsyncMock()
        mock_signaling = AsyncMock()
        mock_signaling.get_turn_credentials.return_value = turn
        mock_signaling.wait_for_answer.return_value = ('v=0\r\nfake-answer', ['candidate:1 1 udp 2113937151 192.168.1.1 12345 typ host'])

        mock_channel = MagicMock()
        mock_peer = AsyncMock()
        mock_peer.create_offer.return_value = ('v=0\r\nfake-offer', ['candidate:2 1 udp 2113937151 192.168.1.2 54321 typ host'])
        mock_peer.wait_for_channel.return_value = mock_channel
        mock_peer.message_queue = asyncio.Queue()

        with (
            patch(LOCAL_HTTP_PATCH, return_value=mock_http),
            patch(LOCAL_WS_SIG_PATCH, return_value=mock_signaling),
            patch(PEER_PATCH, return_value=mock_peer),
        ):
            await session.connect()

            assert session.connected is True
            mock_http.login.assert_called_once()
            mock_signaling.connect.assert_called_once()
            mock_signaling.get_turn_credentials.assert_called_once()
            mock_peer.create_offer.assert_called_once_with(channel_label='ssh')
            mock_signaling.send_offer.assert_called_once()
            mock_signaling.send_ice_candidate.assert_called_once()
            mock_signaling.wait_for_answer.assert_called_once()
            mock_peer.accept_answer.assert_called_once()
            mock_signaling.send_sdp_complete.assert_called_once()

    async def test_connect_cloud_flow(self, cloud_config: CloudConfig, ssh_config: SSHConfig) -> None:
        """Test cloud connect passes fallback TURN to CloudSSHSignaling."""
        session = SSHSession(cloud_config, ssh_config)

        turn = TurnCredentials(
            stun_urls=['stun:stun.example.com:3478'],
            turn_urls=['turn:turn.example.com:3478'],
            turn_username='user',
            turn_password='pass',
        )

        mock_cloud_http = AsyncMock()
        mock_cloud_http.get_turn_credentials.return_value = turn

        mock_cloud_client = AsyncMock()
        mock_cloud_client._cloud_http = mock_cloud_http

        mock_signaling = AsyncMock()
        mock_signaling.get_turn_credentials.return_value = turn
        mock_signaling.poll_sdp_offer.return_value = 'v=0\r\nfake-offer'

        mock_channel = MagicMock()
        mock_peer = AsyncMock()
        mock_peer.accept_offer.return_value = 'v=0\r\nfake-answer'
        mock_peer.wait_for_channel.return_value = mock_channel
        mock_peer.message_queue = asyncio.Queue()

        with (
            patch(CLOUD_CLIENT_PATCH, return_value=mock_cloud_client),
            patch(CLOUD_SSH_SIG_PATCH, return_value=mock_signaling) as mock_sig_cls,
            patch(PEER_PATCH, return_value=mock_peer),
        ):
            await session.connect()

            assert session.connected is True
            mock_cloud_client.connect.assert_called_once()
            mock_sig_cls.assert_called_once()
            call_kwargs = mock_sig_cls.call_args.kwargs
            assert call_kwargs.get('fallback_turn') == turn

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

    async def test_close_cloud_cleans_up(self, cloud_config: CloudConfig, ssh_config: SSHConfig) -> None:
        """Close on cloud session should clean up cloud client too."""
        session = SSHSession(cloud_config, ssh_config)

        mock_signaling = AsyncMock()
        mock_peer = AsyncMock()
        mock_cloud_client = AsyncMock()

        session._signaling = mock_signaling
        session._peer = mock_peer
        session._cloud_client = mock_cloud_client
        session._uuid = 'test-uuid'
        session._connected = True

        await session.close()

        assert session.connected is False
        mock_cloud_client.close.assert_called_once()
