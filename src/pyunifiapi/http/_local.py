"""HTTP client for local UniFi controller REST API with cookie auth."""

from __future__ import annotations

import logging

import httpx
import pyotp

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
        """Authenticate with the controller using username/password.

        Supports two 2FA flows (auto-detected when ``totp_secret`` is set):

        - **SSO two-step**: first login returns HTTP 499 with an ``mfaCookie``
          in the JSON body. The cookie is set on the client and a second login
          is sent with the TOTP code in the ``token`` field.
        - **Local 2FA fallback**: first login raises an auth error. A second
          login is sent with the TOTP code in the ``ubic_2fa_token`` field.

        When no ``totp_secret`` is configured, a single login is attempted.
        """
        client = await self._ensure_client()
        payload: dict = {
            'username': self._config.username,
            'password': self._config.password,
            'rememberMe': True,
        }

        # Always attempt login without any 2FA token first to detect auth flow
        try:
            resp = await client.post(API_LOGIN, json=payload)
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to controller at {self.base_url}: {e}') from e

        if resp.status_code == 200:
            self._complete_login(resp)
            return

        if resp.status_code == 499 and self._config.totp_secret:
            # SSO two-step flow: extract MFA cookie from 499 response body
            await self._login_sso_2fa(client, payload, resp)
            return

        if self._config.totp_secret:
            # Local 2FA fallback: retry with ubic_2fa_token
            await self._login_local_2fa(client, payload)
            return

        raise AuthenticationError(f'Login failed with status {resp.status_code}: {resp.text}')

    async def _login_sso_2fa(self, client: httpx.AsyncClient, payload: dict, mfa_response: httpx.Response) -> None:
        """Complete SSO two-step 2FA using the mfaCookie from the 499 response."""
        logger.debug('SSO MFA challenge received, performing two-step auth')
        try:
            body = mfa_response.json()
            mfa_cookie_str: str = body.get('data', {}).get('mfaCookie', '')
        except (ValueError, AttributeError):
            raise AuthenticationError(f'Login failed with status {mfa_response.status_code}: unable to parse MFA response')

        if not mfa_cookie_str or '=' not in mfa_cookie_str:
            raise AuthenticationError(f'Login failed with status {mfa_response.status_code}: missing or malformed mfaCookie')

        cookie_name, cookie_val = mfa_cookie_str.split('=', 1)
        client.cookies.set(cookie_name, cookie_val)

        assert self._config.totp_secret is not None
        token = pyotp.TOTP(self._config.totp_secret).now()
        try:
            resp = await client.post(API_LOGIN, json={**payload, 'token': token})
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to controller at {self.base_url}: {e}') from e

        if resp.status_code == 200:
            self._complete_login(resp)
        else:
            raise AuthenticationError(f'Login failed with status {resp.status_code}: {resp.text}')

    async def _login_local_2fa(self, client: httpx.AsyncClient, payload: dict) -> None:
        """Retry login with a TOTP code in the ubic_2fa_token field (local 2FA)."""
        logger.debug('Retrying login with local 2FA token')
        assert self._config.totp_secret is not None
        token = pyotp.TOTP(self._config.totp_secret).now()
        try:
            resp = await client.post(API_LOGIN, json={**payload, 'ubic_2fa_token': token})
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to controller at {self.base_url}: {e}') from e

        if resp.status_code == 200:
            self._complete_login(resp)
        else:
            raise AuthenticationError(f'Login failed with status {resp.status_code}: {resp.text}')

    def _complete_login(self, resp: httpx.Response) -> None:
        """Extract CSRF token and mark session as authenticated."""
        self._csrf_token = resp.headers.get('x-csrf-token') or resp.cookies.get('csrf_token')
        self._authenticated = True
        logger.info('Authenticated with controller at %s', self.base_url)

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
