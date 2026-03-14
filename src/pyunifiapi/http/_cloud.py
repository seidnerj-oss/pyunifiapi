"""HTTP client for Ubiquiti cloud SSO and Site Manager API.

Authentication flow:
1. SSO login at sso.ubnt.com -> sets UBIC_AUTH cookie
2. POST /create-credentials with cookie -> returns AWS STS credentials + TURN credentials
3. All subsequent API calls use AWS SigV4 request signing
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import logging
from urllib.parse import quote, urlparse

import httpx

from pyunifiapi._constants import CLOUD_ACCESS_URL, CLOUD_SSO_URL
from pyunifiapi._exceptions import ApiConnectionError, AuthenticationError
from pyunifiapi._types import CloudConfig, TurnCredentials

logger = logging.getLogger(__name__)


def _sign_aws_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    service: str = 'execute-api',
) -> dict[str, str]:
    """Generate AWS SigV4 authorization headers for an HTTP request."""
    now = datetime.datetime.now(datetime.UTC)
    datestamp = now.strftime('%Y%m%d')
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')

    parsed = urlparse(url)
    canonical_uri = quote(parsed.path or '/', safe='/')
    # Query parameters must be sorted by key for SigV4
    query_pairs = sorted(pair.split('=', 1) for pair in parsed.query.split('&') if pair)
    canonical_querystring = '&'.join(f'{quote(k, safe="")}={quote(v, safe="")}' for k, v in query_pairs) if query_pairs else ''

    # Ensure required headers
    headers_to_sign = {
        'host': parsed.hostname,
        'x-amz-date': amz_date,
        'x-amz-security-token': session_token,
    }

    signed_header_names = sorted(headers_to_sign.keys())
    signed_headers = ';'.join(signed_header_names)
    canonical_headers = ''.join(f'{k}:{headers_to_sign[k]}\n' for k in signed_header_names)

    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_request = '\n'.join(
        [
            method.upper(),
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f'{datestamp}/{region}/{service}/aws4_request'
    string_to_sign = '\n'.join(
        [
            'AWS4-HMAC-SHA256',
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest(),
        ]
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    signing_key = _sign(_sign(_sign(_sign(f'AWS4{secret_key}'.encode(), datestamp), region), service), 'aws4_request')

    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    authorization = f'AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, ' f'SignedHeaders={signed_headers}, ' f'Signature={signature}'

    return {
        'Authorization': authorization,
        'X-Amz-Date': amz_date,
        'X-Amz-Security-Token': session_token,
    }


class CloudHttpTransport:
    """HTTP client for Ubiquiti cloud SSO authentication and Site Manager API.

    Handles SSO login to sso.ubnt.com, credential exchange at
    cloudaccess.svc.ui.com, and AWS SigV4-signed API requests.
    """

    def __init__(self, config: CloudConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False
        self._aws_credentials: dict | None = None
        self._turn_credentials: TurnCredentials | None = None

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
                    'Origin': 'https://account.ui.com',
                    'Referer': 'https://account.ui.com/',
                },
            )
        return self._client

    async def sso_login(self) -> None:
        """Login to Ubiquiti SSO and obtain API credentials.

        Three-phase flow:
        1. POST credentials to /login. Returns 200 (no 2FA) or the 2FA
           challenge with authenticator list.
        2. If 2FA required, POST TOTP code to /login/2fa.
        3. Exchange UBIC_AUTH cookie for AWS STS credentials via /create-credentials.
        """
        client = await self._ensure_client()

        payload: dict = {
            'user': self._config.username,
            'password': self._config.password,
            'remember_me': True,
        }

        try:
            resp = await client.post(f'{CLOUD_SSO_URL}/login', json=payload)
        except httpx.ConnectError as e:
            raise ApiConnectionError(f'Cannot connect to Ubiquiti SSO: {e}') from e

        if resp.status_code == 200:
            logger.info('Authenticated with Ubiquiti SSO (no 2FA)')
        elif self._config.totp_secret:
            # 2FA challenge - submit TOTP code to /login/2fa
            import pyotp

            token = pyotp.TOTP(self._config.totp_secret).now()
            logger.debug('SSO 2FA challenge received, submitting TOTP to /login/2fa')
            resp = await client.post(f'{CLOUD_SSO_URL}/login/2fa', json={'token': token})

            if resp.status_code == 200:
                logger.info('Authenticated with Ubiquiti SSO (2FA)')
            else:
                raise AuthenticationError(f'SSO 2FA failed with status {resp.status_code}: {resp.text}')
        else:
            raise AuthenticationError(f'SSO login failed with status {resp.status_code}: {resp.text}')

        # Exchange SSO cookie for AWS credentials
        await self._create_credentials()

    async def _create_credentials(self) -> None:
        """Exchange SSO cookie for AWS STS credentials and TURN credentials."""
        client = await self._ensure_client()
        # Forward SSO cookies cross-domain (httpx doesn't do this automatically)
        cookie_header = '; '.join(f'{name}={value}' for name, value in client.cookies.items())
        resp = await client.post(
            f'{CLOUD_ACCESS_URL}/create-credentials',
            json={'withTurn': True},
            headers={'Cookie': cookie_header, 'Content-Type': 'application/json'},
        )

        if resp.status_code != 200:
            raise AuthenticationError(f'Failed to create cloud credentials: {resp.status_code} {resp.text}')

        data = resp.json()
        self._aws_credentials = {
            'access_key': data['accessKeyId'],
            'secret_key': data['secretKey'],
            'session_token': data['sessionToken'],
            'region': data.get('region', 'us-west-2'),
            'identity_id': data.get('identityId', ''),
            'expiration': data.get('expiration'),
        }

        turn = data.get('turnCredentials', {})
        if turn:
            self._turn_credentials = TurnCredentials(
                stun_urls=[u for u in turn.get('uris', []) if u.startswith('stun:')],
                turn_urls=[u for u in turn.get('uris', []) if not u.startswith('stun:')],
                turn_username=turn.get('username', ''),
                turn_password=turn.get('password', ''),
            )

        self._authenticated = True
        logger.info('Cloud API credentials obtained (region=%s)', self._aws_credentials['region'])

    async def _signed_request(self, method: str, path: str) -> httpx.Response:
        """Make an AWS SigV4-signed request to the cloudaccess API (no body)."""
        return await self._signed_request_with_body(method, path)

    async def _signed_request_with_body(self, method: str, path: str, json_body: dict | None = None) -> httpx.Response:
        """Make an AWS SigV4-signed request to the cloudaccess API."""
        if not self._authenticated or not self._aws_credentials:
            await self.sso_login()

        assert self._aws_credentials is not None
        client = await self._ensure_client()
        url = f'{CLOUD_ACCESS_URL}{path}'

        import json as json_mod

        body = json_mod.dumps(json_body).encode('utf-8') if json_body else b''

        sig_headers = _sign_aws_request(
            method=method,
            url=url,
            headers={},
            body=body,
            access_key=self._aws_credentials['access_key'],
            secret_key=self._aws_credentials['secret_key'],
            session_token=self._aws_credentials['session_token'],
            region=self._aws_credentials['region'],
        )

        if json_body:
            sig_headers['Content-Type'] = 'application/json'
            return await client.request(method, url, headers=sig_headers, content=body)
        return await client.request(method, url, headers=sig_headers)

    async def list_hosts(self) -> list[dict]:
        """List cloud-connected controllers (hosts) from the Site Manager API."""
        resp = await self._signed_request('GET', '/api/v1/hosts?type=uos&withUserData=true&pageSize=350')
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get('data', [])

    async def list_devices(self) -> list[dict]:
        """List all devices across all controllers from the Site Manager API."""
        resp = await self._signed_request('GET', '/api/v1/devices?includeCustomPermissions=true&withPermissions=true')
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get('data', [])

    async def list_sites(self) -> list[dict]:
        """List all sites across all controllers from the Site Manager API."""
        resp = await self._signed_request('GET', '/api/v1/sites?includeStatistics=true')
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get('data', [])

    async def get_turn_credentials(self, device_id: str) -> TurnCredentials:
        """Get TURN credentials for WebRTC.

        Returns cached credentials from the initial create-credentials call,
        or fetches them from a dedicated endpoint if not cached.
        """
        if not self._authenticated:
            await self.sso_login()
        if self._turn_credentials:
            return self._turn_credentials

        # Fetch TURN credentials via signed API request
        resp = await self._signed_request('GET', f'/api/airos/v1/unifi/turn/creds?username={device_id}')
        if resp.status_code == 200:
            data = resp.json()
            self._turn_credentials = TurnCredentials(
                stun_urls=[u for u in data.get('uris', []) if u.startswith('stun:')],
                turn_urls=[u for u in data.get('uris', []) if not u.startswith('stun:')],
                turn_username=data.get('username', ''),
                turn_password=data.get('password', ''),
            )
            return self._turn_credentials

        raise AuthenticationError(f'Failed to get TURN credentials: {resp.status_code} {resp.text}')

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._authenticated = False
        self._aws_credentials = None
        self._turn_credentials = None
