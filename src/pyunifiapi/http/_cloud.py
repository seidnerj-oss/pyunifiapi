"""HTTP client for Ubiquiti cloud SSO and device API."""

from __future__ import annotations

import logging

import httpx

from pyunifiapi._constants import CLOUD_DEVICE_URL, CLOUD_SSO_URL
from pyunifiapi._exceptions import ApiConnectionError, AuthenticationError
from pyunifiapi._types import CloudConfig, TurnCredentials

logger = logging.getLogger(__name__)


class CloudHttpTransport:
    """HTTP client for Ubiquiti cloud SSO authentication and device API.

    Handles SSO login to sso.ubnt.com, device listing from
    device-airos.svc.ubnt.com, and TURN credential retrieval.
    """

    def __init__(self, config: CloudConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False

    async def __aenter__(self) -> CloudHttpTransport:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                cookies=httpx.Cookies(),
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                headers={
                    'Origin': 'https://account.ubnt.com',
                    'Referer': 'https://account.ubnt.com/login?redirect=https://unifi.ui.com',
                },
            )
        return self._client

    async def sso_login(self) -> None:
        """Login to Ubiquiti SSO (sso.ubnt.com).

        If the cloud config includes a TOTP secret, generates a
        one-time code and includes it as ``ubic_2fa_token`` in the
        login payload.
        """
        client = await self._ensure_client()
        payload: dict = {
            'user': self._config.username,
            'password': self._config.password,
        }
        if self._config.totp_secret:
            import pyotp

            payload['ubic_2fa_token'] = pyotp.TOTP(self._config.totp_secret).now()

        try:
            resp = await client.post(f'{CLOUD_SSO_URL}/login', json=payload)
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to Ubiquiti SSO: {e}') from e

        if resp.status_code == 200:
            self._authenticated = True
            logger.info('Authenticated with Ubiquiti SSO')
        else:
            raise AuthenticationError(f'SSO login failed with status {resp.status_code}: {resp.text}')

    async def list_devices(self) -> list[dict]:
        """List devices from cloud API."""
        if not self._authenticated:
            await self.sso_login()
        client = await self._ensure_client()
        resp = await client.get(f'{CLOUD_DEVICE_URL}/devices')
        resp.raise_for_status()
        result: list[dict] = resp.json()
        return result

    async def get_turn_credentials(self, device_id: str) -> TurnCredentials:
        """Get TURN credentials for WebRTC to a specific device."""
        if not self._authenticated:
            await self.sso_login()
        client = await self._ensure_client()
        resp = await client.get(f'{CLOUD_DEVICE_URL}/turn/creds', params={'username': device_id})
        resp.raise_for_status()
        data = resp.json()
        return TurnCredentials(
            stun_urls=[u for u in data.get('uris', []) if u.startswith('stun:')],
            turn_urls=[u for u in data.get('uris', []) if u.startswith('turn:')],
            turn_username=data.get('username', ''),
            turn_password=data.get('password', ''),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._authenticated = False
