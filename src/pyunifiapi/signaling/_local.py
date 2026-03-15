"""SDP/ICE signaling for SSH sessions via the local UniFi controller REST API.

Implements the 6-step signaling flow:
1. Get TURN credentials from controller
2. Tell device to build SSH session
3. Poll for device's SDP offer
4. Send our SDP answer back
5. (WebRTC connection established)
6. Close SSH session
"""

from __future__ import annotations

import asyncio
import logging
import re

from pyunifiapi._constants import API_CMD_DEVMGR, API_CMD_SDN, SDP_POLL_INTERVAL, SDP_POLL_MAX_RETRIES, SSH_SESSION_TTL
from pyunifiapi._exceptions import SDPPollTimeoutError, SignalingError
from pyunifiapi._types import TurnCredentials
from pyunifiapi.http._local import LocalHttpTransport

logger = logging.getLogger(__name__)


class LocalSignaling:
    """SDP/ICE signaling for SSH sessions via the local UniFi controller REST API.

    Uses the controller's /api/s/{site}/cmd/devmgr and /cmd/sdn endpoints
    to orchestrate the WebRTC handshake between us and the target device.
    """

    def __init__(self, http: LocalHttpTransport, site: str = 'default', is_unifi_os: bool = False) -> None:
        self._http = http
        self._site = site
        self._is_unifi_os = is_unifi_os

    def _path(self, template: str) -> str:
        """Format an API path, prepending /proxy/network for UniFi OS controllers."""
        path = template.format(site=self._site)
        return f'/proxy/network{path}' if self._is_unifi_os else path

    def _devmgr_path(self) -> str:
        return self._path(API_CMD_DEVMGR)

    def _sdn_path(self) -> str:
        return self._path(API_CMD_SDN)

    async def get_turn_credentials(self) -> TurnCredentials:
        """Request STUN/TURN credentials from the controller.

        POST /api/s/{site}/cmd/sdn with cmd=get-turn-credentials.
        """
        resp = await self._http.post(self._sdn_path(), json={'cmd': 'get-turn-credentials'})
        data = resp.json()

        if resp.status_code != 200 or 'data' not in data:
            raise SignalingError(f'Failed to get TURN credentials: {resp.status_code} {data}')

        creds = data['data'][0] if data['data'] else {}
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
        """Tell the device to prepare an SSH session.

        POST /api/s/{site}/cmd/devmgr with cmd=build-ssh-session.
        The device will start generating its SDP offer.
        """
        # Strip protocol prefix from STUN/TURN URLs (controller expects host:port only)
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

        resp = await self._http.post(self._devmgr_path(), json=payload)
        data = resp.json()

        if resp.status_code != 200:
            raise SignalingError(f'Failed to build SSH session: {resp.status_code} {data}')

        logger.info('SSH session build requested for device %s (uuid: %s)', mac, uuid)

    async def poll_sdp_offer(
        self,
        mac: str,
        uuid: str,
        max_retries: int = SDP_POLL_MAX_RETRIES,
        interval: float = SDP_POLL_INTERVAL,
    ) -> str:
        """Poll for the device's SDP offer.

        POST /api/s/{site}/cmd/devmgr with cmd=get-sdp-offer.
        Retries up to max_retries times with interval seconds between attempts.

        Returns:
            The SDP offer string from the device.

        Raises:
            SDPPollTimeoutError: If no offer received after all retries.
        """
        payload = {
            'cmd': 'get-sdp-offer',
            'mac': mac.lower(),
            'uuid': uuid,
        }

        for attempt in range(1, max_retries + 1):
            resp = await self._http.post(self._devmgr_path(), json=payload)
            data = resp.json()

            if resp.status_code == 200 and data.get('data'):
                sdp_offer: str | None = data['data'][0].get('ssh_sdp_offer')
                if sdp_offer:
                    logger.info('Received SDP offer from device %s (attempt %d/%d)', mac, attempt, max_retries)
                    return sdp_offer

            logger.debug('SDP offer not ready (attempt %d/%d), retrying in %.1fs', attempt, max_retries, interval)
            await asyncio.sleep(interval)

        raise SDPPollTimeoutError(f'No SDP offer from device {mac} after {max_retries} attempts')

    async def send_sdp_answer(self, mac: str, uuid: str, sdp_answer: str) -> None:
        """Send our SDP answer to the device.

        POST /api/s/{site}/cmd/devmgr with cmd=ssh-sdp-answer.
        """
        payload = {
            'cmd': 'ssh-sdp-answer',
            'mac': mac.lower(),
            'uuid': uuid,
            'sdpanswer': sdp_answer,
        }

        resp = await self._http.post(self._devmgr_path(), json=payload)
        if resp.status_code != 200:
            raise SignalingError(f'Failed to send SDP answer: {resp.status_code} {resp.text}')

        logger.info('SDP answer sent to device %s', mac)

    async def close_ssh_session(self, mac: str, uuid: str) -> None:
        """Close the SSH session on the controller side.

        POST /api/s/{site}/cmd/devmgr with cmd=close-ssh-session.
        """
        payload = {
            'cmd': 'close-ssh-session',
            'mac': mac.lower(),
            'uuid': uuid,
        }

        resp = await self._http.post(self._devmgr_path(), json=payload)
        if resp.status_code != 200:
            logger.warning('Failed to close SSH session: %s %s', resp.status_code, resp.text)
        else:
            logger.info('SSH session closed for device %s', mac)
