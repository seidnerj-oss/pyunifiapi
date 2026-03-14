"""SDP/ICE signaling for SSH sessions via cloud WebRTC API tunnel.

Same signaling flow as _local.py but routes API calls through a
CloudClient's WebRTC data channel instead of direct HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import re

from pyunifiapi._constants import SDP_POLL_INTERVAL, SDP_POLL_MAX_RETRIES, SSH_SESSION_TTL
from pyunifiapi._exceptions import SDPPollTimeoutError, SignalingError
from pyunifiapi._types import TurnCredentials
from pyunifiapi.cloud import CloudClient

logger = logging.getLogger(__name__)


class CloudSSHSignaling:
    """SDP/ICE signaling for SSH sessions via cloud WebRTC API tunnel.

    Uses the same controller endpoints as LocalSignaling but sends
    them through CloudClient.request() over the WebRTC data channel.
    """

    def __init__(self, cloud_client: CloudClient, site: str = 'default') -> None:
        self._client = cloud_client
        self._site = site

    def _devmgr_path(self) -> str:
        return f'/proxy/network/api/s/{self._site}/cmd/devmgr'

    def _sdn_path(self) -> str:
        return f'/proxy/network/api/s/{self._site}/cmd/sdn'

    async def get_turn_credentials(self) -> TurnCredentials:
        """Request STUN/TURN credentials from the controller via cloud tunnel."""
        data = await self._client.request('POST', self._sdn_path(), {'cmd': 'get-turn-credentials'})

        creds_list = data.get('data', [data]) if isinstance(data, dict) else data
        creds = creds_list[0] if creds_list else {}
        stun_urls = [u for u in creds.get('uris', []) if u.startswith('stun:')]
        turn_urls = [u for u in creds.get('uris', []) if u.startswith('turn:')]

        return TurnCredentials(
            stun_urls=stun_urls,
            turn_urls=turn_urls,
            turn_username=creds.get('username', ''),
            turn_password=creds.get('password', ''),
        )

    async def build_ssh_session(
        self,
        mac: str,
        uuid: str,
        turn: TurnCredentials,
        username: str = 'ubnt',
        password: str = 'ubnt',
    ) -> None:
        """Tell the device to prepare an SSH session via cloud tunnel."""
        stun = re.sub(r'^stun:', '', turn.stun_urls[0]) if turn.stun_urls else ''
        turn_url = re.sub(r'^turns?:', '', turn.turn_urls[0]) if turn.turn_urls else ''

        payload = {
            'cmd': 'build-ssh-session',
            'mac': mac.lower(),
            'uuid': uuid,
            'ttl': str(SSH_SESSION_TTL),
            'stun': stun,
            'turn': turn_url,
            'username': turn.turn_username,
            'password': turn.turn_password,
        }

        await self._client.request('POST', self._devmgr_path(), payload)
        logger.info('SSH session build requested for device %s (uuid: %s)', mac, uuid)

    async def poll_sdp_offer(
        self,
        mac: str,
        uuid: str,
        max_retries: int = SDP_POLL_MAX_RETRIES,
        interval: float = SDP_POLL_INTERVAL,
    ) -> str:
        """Poll for the device's SDP offer via cloud tunnel."""
        payload = {
            'cmd': 'get-sdp-offer',
            'mac': mac.lower(),
            'uuid': uuid,
        }

        for attempt in range(1, max_retries + 1):
            data = await self._client.request('POST', self._devmgr_path(), payload)

            data_list = data.get('data', []) if isinstance(data, dict) else []
            if data_list:
                sdp_offer: str | None = data_list[0].get('ssh_sdp_offer')
                if sdp_offer:
                    logger.info('Received SDP offer from device %s (attempt %d/%d)', mac, attempt, max_retries)
                    return sdp_offer

            logger.debug('SDP offer not ready (attempt %d/%d), retrying in %.1fs', attempt, max_retries, interval)
            await asyncio.sleep(interval)

        raise SDPPollTimeoutError(f'No SDP offer from device {mac} after {max_retries} attempts')

    async def send_sdp_answer(self, mac: str, uuid: str, sdp_answer: str) -> None:
        """Send our SDP answer to the device via cloud tunnel."""
        payload = {
            'cmd': 'ssh-sdp-answer',
            'mac': mac.lower(),
            'uuid': uuid,
            'sdpanswer': sdp_answer,
        }

        await self._client.request('POST', self._devmgr_path(), payload)
        logger.info('SDP answer sent to device %s', mac)

    async def close_ssh_session(self, mac: str, uuid: str) -> None:
        """Close the SSH session on the controller side via cloud tunnel."""
        payload = {
            'cmd': 'close-ssh-session',
            'mac': mac.lower(),
            'uuid': uuid,
        }

        try:
            await self._client.request('POST', self._devmgr_path(), payload)
            logger.info('SSH session closed for device %s', mac)
        except Exception:
            logger.warning('Failed to close SSH session for %s', mac)
