"""Tests for the Controller orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pyunifiapi._types import ControllerConfig
from pyunifiapi.controller import Controller
from pyunifiapi.models.device import DeviceRestartRequest


def make_config() -> ControllerConfig:
    return ControllerConfig(host='192.168.1.1', username='admin', password='pass')


def make_json_response(data: list[dict], status: int = 200) -> httpx.Response:
    import json

    content = json.dumps({'meta': {'rc': 'ok'}, 'data': data}).encode()
    return httpx.Response(status_code=status, content=content, headers={'content-type': 'application/json'})


class TestControllerInit:
    def test_handlers_exist(self) -> None:
        ctrl = Controller(make_config())
        assert ctrl.devices is not None
        assert ctrl.clients is not None
        assert ctrl.events is not None
        assert ctrl.wlans is not None
        assert ctrl.sites is not None
        assert ctrl.vouchers is not None
        assert ctrl.port_forwards is not None
        assert ctrl.traffic_rules is not None
        assert ctrl.traffic_routes is not None
        assert ctrl.firewall_zones is not None
        assert ctrl.firewall_policies is not None
        assert ctrl.dpi_apps is not None
        assert ctrl.dpi_groups is not None
        assert ctrl.system_information is not None

    def test_handlers_start_empty(self) -> None:
        ctrl = Controller(make_config())
        assert len(ctrl.devices) == 0
        assert len(ctrl.clients) == 0


class TestControllerConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_transport(self) -> None:
        ctrl = Controller(make_config())
        with patch('pyunifiapi.controller.LocalHttpTransport') as MockTransport:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=make_json_response([]))
            MockTransport.return_value = mock_http
            await ctrl.connect()
            mock_http.login.assert_awaited_once()
            await ctrl.disconnect()


class TestControllerInitialize:
    @pytest.mark.asyncio
    async def test_initialize_populates_handlers(self) -> None:
        ctrl = Controller(make_config())
        mock_http = AsyncMock()

        device_data = [{'mac': 'aa:bb:cc:dd:ee:ff', 'name': 'AP'}]
        client_data = [{'mac': '11:22:33:44:55:66', 'name': 'Phone'}]
        wlan_data = [{'_id': 'w1', 'name': 'MyNet'}]
        sysinfo_data = [{'anonymous_controller_id': 'ctrl1', 'hostname': 'UDM'}]
        pf_data = [{'_id': 'pf1', 'name': 'Web'}]
        event_data = [{'_id': 'e1', 'key': 'EVT_WU_Connected'}]
        site_data = [{'_id': 's1', 'name': 'default'}]

        call_count = 0

        async def mock_get(path: str) -> httpx.Response:
            nonlocal call_count
            if 'stat/device' in path:
                return make_json_response(device_data)
            elif 'stat/sta' in path:
                return make_json_response(client_data)
            elif 'list/wlanconf' in path:
                return make_json_response(wlan_data)
            elif 'stat/sysinfo' in path:
                return make_json_response(sysinfo_data)
            elif 'list/portforward' in path:
                return make_json_response(pf_data)
            elif 'stat/event' in path:
                return make_json_response(event_data)
            elif 'self/sites' in path:
                return make_json_response(site_data)
            return make_json_response([])

        mock_http.get = mock_get
        ctrl._http = mock_http
        ctrl._session.is_unifi_os = False

        await ctrl.initialize()

        assert len(ctrl.devices) == 1
        assert 'aa:bb:cc:dd:ee:ff' in ctrl.devices
        assert len(ctrl.clients) == 1
        assert len(ctrl.wlans) == 1
        assert len(ctrl.system_information) == 1
        assert len(ctrl.port_forwards) == 1
        assert len(ctrl.events) == 1
        assert len(ctrl.sites) == 1


class TestControllerExecute:
    @pytest.mark.asyncio
    async def test_execute_request(self) -> None:
        ctrl = Controller(make_config())
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=make_json_response([{'ok': True}]))
        ctrl._http = mock_http
        ctrl._session.is_unifi_os = False

        req = DeviceRestartRequest.create('aa:bb:cc:dd:ee:ff')
        result = await ctrl.execute(req)

        mock_http.request.assert_awaited_once()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_with_unifi_os(self) -> None:
        ctrl = Controller(make_config())
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=make_json_response([]))
        ctrl._http = mock_http
        ctrl._session.is_unifi_os = True

        req = DeviceRestartRequest.create('aa:bb:cc:dd:ee:ff')
        await ctrl.execute(req)

        call_args = mock_http.request.call_args
        path = call_args[0][1]
        assert path.startswith('/proxy/network')


class TestControllerDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self) -> None:
        ctrl = Controller(make_config())
        mock_http = AsyncMock()
        ctrl._http = mock_http
        await ctrl.disconnect()
        mock_http.close.assert_awaited_once()
        assert ctrl._http is None

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        with patch('pyunifiapi.controller.LocalHttpTransport') as MockTransport:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=make_json_response([]))
            MockTransport.return_value = mock_http
            async with Controller(make_config()) as ctrl:
                assert ctrl._http is not None
            mock_http.close.assert_awaited()
