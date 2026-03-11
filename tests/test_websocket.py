"""Tests for WebSocket client."""

from __future__ import annotations

from pyunifiapi.websocket import WS_PATH_CLASSIC, WS_PATH_UNIFI_OS, WebSocketClient


class TestWebSocketUrl:
    def test_classic_url(self) -> None:
        ws = WebSocketClient(
            host='192.168.1.1',
            port=443,
            site='default',
            session_cookie='abc123',
            is_unifi_os=False,
        )
        assert ws.url == 'wss://192.168.1.1:443/wss/s/default/events'

    def test_unifi_os_url(self) -> None:
        ws = WebSocketClient(
            host='192.168.1.1',
            port=443,
            site='default',
            session_cookie='abc123',
            is_unifi_os=True,
        )
        assert ws.url == 'wss://192.168.1.1:443/proxy/network/wss/s/default/events'

    def test_custom_site(self) -> None:
        ws = WebSocketClient(
            host='10.0.0.1',
            port=8443,
            site='mysite',
            session_cookie='token',
            is_unifi_os=False,
        )
        assert ws.url == 'wss://10.0.0.1:8443/wss/s/mysite/events'


class TestPathTemplates:
    def test_classic_path(self) -> None:
        assert WS_PATH_CLASSIC == '/wss/s/{site}/events'

    def test_unifi_os_path(self) -> None:
        assert WS_PATH_UNIFI_OS == '/proxy/network/wss/s/{site}/events'
