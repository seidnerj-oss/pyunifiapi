"""SDP/ICE signaling for SSH sessions via the local UniFi controller REST API.

Implements the 6-step signaling flow:
1. Get TURN credentials from controller
2. Tell device to build SSH session
3. Wait for the device's SDP offer: Network 11.x pushes it as a ``device:sdp-offer``
   event on the events websocket, older controllers serve it via ``get-sdp-offer``
4. Send our SDP answer back
5. (WebRTC connection established)
6. Close SSH session
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress

from pyunifiapi._constants import API_CMD_DEVMGR, API_CMD_SDN, SDP_POLL_INTERVAL, SDP_POLL_MAX_RETRIES, SSH_SESSION_TTL
from pyunifiapi._exceptions import SDPPollTimeoutError, SignalingError
from pyunifiapi._types import TurnCredentials
from pyunifiapi.http._local import LocalHttpTransport
from pyunifiapi.models.message import MessageKey
from pyunifiapi.websocket import WebSocketClient

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
        self._events_ws: WebSocketClient | None = None
        self._event_offer: asyncio.Task[str | None] | None = None

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
        Returns empty credentials on failure (local SSH works without TURN
        via host ICE candidates).
        """
        try:
            resp = await self._http.post(self._sdn_path(), json={'cmd': 'get-turn-credentials'})
            data = resp.json()

            if resp.status_code != 200 or 'data' not in data:
                logger.debug('TURN credentials not available (status %s), proceeding without', resp.status_code)
                return TurnCredentials()

            creds = data['data'][0] if data['data'] else {}
            stun_urls = [u for u in creds.get('uris', []) if u.startswith('stun:')]
            turn_urls = [u for u in creds.get('uris', []) if u.startswith('turn:')]

            return TurnCredentials(
                stun_urls=stun_urls,
                turn_urls=turn_urls,
                turn_username=creds.get('username', ''),
                turn_password=creds.get('password', ''),
            )
        except Exception as e:
            logger.debug('Failed to get TURN credentials: %s, proceeding without', e)
            return TurnCredentials()

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
        The device will start generating its SDP offer. The events websocket is
        opened first so a ``device:sdp-offer`` push cannot be missed.
        """
        await self._listen_for_offer_event(uuid)

        # Strip protocol prefix and query params from STUN/TURN URLs (device expects host:port only)
        stun = re.sub(r'^stun:', '', turn.stun_urls[0]).split('?')[0] if turn.stun_urls else ''
        turn_url = re.sub(r'^turns?:', '', turn.turn_urls[0]).split('?')[0] if turn.turn_urls else ''

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

        try:
            resp = await self._http.post(self._devmgr_path(), json=payload)
            data = resp.json()

            if resp.status_code != 200:
                raise SignalingError(f'Failed to build SSH session: {resp.status_code} {data}')
        except BaseException:
            await self.close()
            raise

        logger.info('SSH session build requested for device %s (uuid: %s)', mac, uuid)

    async def _listen_for_offer_event(self, uuid: str) -> None:
        """Open the events websocket and start waiting for this session's offer event.

        A connection failure is logged and leaves get-sdp-offer polling as the only source.
        """
        cookie = self._http.get_cookies().get('TOKEN', '')
        config = self._http._config
        ws = WebSocketClient(
            host=config.host,
            port=config.port,
            site=self._site,
            session_cookie=cookie,
            is_unifi_os=self._is_unifi_os,
            ssl_verify=config.ssl_verify,
        )
        try:
            await ws.connect()
        except Exception as e:
            logger.warning('Events websocket unavailable (%s), relying on get-sdp-offer polling', e)
            return

        self._events_ws = ws
        self._event_offer = asyncio.create_task(self._wait_for_offer_event(ws, uuid))

    @staticmethod
    async def _wait_for_offer_event(ws: WebSocketClient, uuid: str) -> str | None:
        """Return the SDP from the device:sdp-offer event matching uuid, or None if the stream ends."""
        async for message in ws.listen():
            if message.meta.message_key != MessageKey.SDP_OFFER:
                continue
            for item in message.data:
                if item.get('ssh_sdp_offer_id') == uuid and item.get('ssh_sdp_offer'):
                    return str(item['ssh_sdp_offer'])
        return None

    async def poll_sdp_offer(
        self,
        mac: str,
        uuid: str,
        max_retries: int = SDP_POLL_MAX_RETRIES,
        interval: float = SDP_POLL_INTERVAL,
    ) -> str:
        """Wait for the device's SDP offer from whichever source delivers first.

        Races the ``device:sdp-offer`` websocket event started by build_ssh_session
        (Network 11.x) against get-sdp-offer polling (older controllers), then
        cancels the loser and closes the websocket.

        Returns:
            The SDP offer string from the device.

        Raises:
            SDPPollTimeoutError: If neither source delivers within the polling budget.
        """
        event_offer = self._event_offer
        if event_offer is None:
            return await self._poll_sdp_offer(mac, uuid, max_retries, interval)

        poll = asyncio.create_task(self._poll_sdp_offer(mac, uuid, max_retries, interval))
        try:
            pending: set[asyncio.Task[str | None]] = {poll, event_offer}
            while True:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                if event_offer in done:
                    if not event_offer.cancelled() and event_offer.exception() is None and (sdp := event_offer.result()):
                        logger.info('Received SDP offer from device %s via websocket event', mac)
                        return sdp
                    logger.debug('Events websocket ended without an offer, continuing to poll')
                if poll in done:
                    return poll.result()  # type: ignore[return-value]
        finally:
            if not poll.done():
                poll.cancel()
                with suppress(asyncio.CancelledError):
                    await poll
            await self.close()

    async def _poll_sdp_offer(self, mac: str, uuid: str, max_retries: int, interval: float) -> str:
        """Poll POST /api/s/{site}/cmd/devmgr with cmd=get-sdp-offer up to max_retries times."""
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

    async def close(self) -> None:
        """Stop waiting for an offer event and close the events websocket, if open."""
        event_offer, self._event_offer = self._event_offer, None
        if event_offer is not None:
            event_offer.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await event_offer

        ws, self._events_ws = self._events_ws, None
        if ws is not None:
            await ws.close()
