"""HTTP client for local UniFi controller REST API with cookie auth."""

from __future__ import annotations

import logging

import httpx

from pyunifiapi._constants import API_LOGIN
from pyunifiapi._exceptions import ApiConnectionError, AuthenticationError
from pyunifiapi._types import ControllerConfig

logger = logging.getLogger(__name__)


class LocalHttpTransport:
    """HTTP client for local UniFi controller with cookie-based authentication.

    Handles login, session cookies, CSRF tokens, and auto-reauth on 401.
    Uses SSL verification disabled by default (self-signed controller certs).
    """

    def __init__(self, config: ControllerConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._csrf_token: str | None = None
        self._authenticated = False

    async def __aenter__(self) -> LocalHttpTransport:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @property
    def base_url(self) -> str:
        return f'https://{self._config.host}:{self._config.port}'

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                verify=self._config.ssl_verify,
                cookies=httpx.Cookies(),
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    async def login(self) -> None:
        """Authenticate with the controller using username/password."""
        client = await self._ensure_client()
        try:
            resp = await client.post(
                API_LOGIN,
                json={
                    'username': self._config.username,
                    'password': self._config.password,
                    'rememberMe': True,
                },
            )
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to controller at {self.base_url}: {e}') from e

        if resp.status_code == 200:
            self._csrf_token = resp.headers.get('x-csrf-token') or resp.cookies.get('csrf_token')
            self._authenticated = True
            logger.info('Authenticated with controller at %s', self.base_url)
        else:
            raise AuthenticationError(f'Login failed with status {resp.status_code}: {resp.text}')

    async def request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        """Make an authenticated request to the controller.

        Auto-reauthenticates on 401 responses.
        """
        if not self._authenticated:
            await self.login()

        client = await self._ensure_client()
        headers = {}
        if self._csrf_token:
            headers['x-csrf-token'] = self._csrf_token

        resp = await client.request(method, path, json=json, headers=headers)

        # Re-auth on 401 or explicit login-required error
        if resp.status_code == 401:
            logger.debug('Got 401, re-authenticating')
            self._authenticated = False
            await self.login()
            headers = {}
            if self._csrf_token:
                headers['x-csrf-token'] = self._csrf_token
            resp = await client.request(method, path, json=json, headers=headers)

        return resp

    async def get(self, path: str) -> httpx.Response:
        """Make an authenticated GET request."""
        return await self.request('GET', path)

    async def post(self, path: str, json: dict | None = None) -> httpx.Response:
        """Make an authenticated POST request."""
        return await self.request('POST', path, json=json)

    async def put(self, path: str, json: dict | None = None) -> httpx.Response:
        """Make an authenticated PUT request."""
        return await self.request('PUT', path, json=json)

    async def delete(self, path: str) -> httpx.Response:
        """Make an authenticated DELETE request."""
        return await self.request('DELETE', path)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._authenticated = False
