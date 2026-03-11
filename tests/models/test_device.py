"""Tests for Device model and request classes."""

from __future__ import annotations

from pyunifiapi.models.device import (
    Device,
    DeviceListRequest,
    DeviceLocateRequest,
    DeviceRestartRequest,
    DeviceSetLedStatus,
    DeviceState,
)

SAMPLE_DEVICE = {
    '_id': '507f1f77bcf86cd799439011',
    'mac': 'aa:bb:cc:dd:ee:ff',
    'name': 'Living Room AP',
    'model': 'U6LR',
    'type': 'uap',
    'serial': 'ABC123',
    'site_id': '5a32aa4ee4b0412345678901',
    'version': '6.5.28',
    'state': 1,
    'adopted': True,
    'ip': '192.168.1.100',
    'uptime': 86400,
    'last_seen': 1700000000,
    'num_sta': 12,
    'guest-num_sta': 3,
    'led_override': 'on',
    'led_override_color': '#0000FF',
    'led_override_color_brightness': 75,
    'hw_caps': 4,
    'system-stats': {'cpu': '15.2', 'mem': '42.1'},
    'port_table': [{'port_idx': 1, 'name': 'eth0'}],
    'outlet_table': [],
    'radio_table': [{'radio': 'ng', 'channel': 6}],
    'temperatures': [{'name': 'CPU', 'value': 55.0}],
    'power_source': 'poe',
}


class TestDevice:
    def test_identity(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.id == '507f1f77bcf86cd799439011'
        assert device.mac == 'aa:bb:cc:dd:ee:ff'
        assert device.name == 'Living Room AP'
        assert device.model == 'U6LR'
        assert device.type == 'uap'
        assert device.serial == 'ABC123'
        assert device.site_id == '5a32aa4ee4b0412345678901'

    def test_state(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.state == DeviceState.CONNECTED
        assert device.adopted is True
        assert device.uptime == 86400
        assert device.last_seen == 1700000000

    def test_network(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.ip == '192.168.1.100'
        assert device.fw_version == '6.5.28'

    def test_statistics(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.connected_clients == 12
        assert device.guest_clients == 3

    def test_led(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.led_override == 'on'
        assert device.led_override_color == '#0000FF'
        assert device.led_override_color_brightness == 75

    def test_supports_led_ring(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.supports_led_ring is True

        device_no_ring = Device({'hw_caps': 0})
        assert device_no_ring.supports_led_ring is False

    def test_system_stats(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.cpu_usage == 15.2
        assert device.mem_usage == 42.1

    def test_tables(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert len(device.port_table) == 1
        assert device.port_table[0]['port_idx'] == 1
        assert device.outlet_table == []
        assert len(device.radio_table) == 1

    def test_misc(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert device.power_source == 'poe'
        assert len(device.temperatures) == 1

    def test_defaults(self) -> None:
        device = Device({})
        assert device.mac == ''
        assert device.name == ''
        assert device.state == DeviceState.DISCONNECTED
        assert device.adopted is False
        assert device.connected_clients == 0
        assert device.supports_led_ring is False

    def test_repr(self) -> None:
        device = Device(SAMPLE_DEVICE)
        assert repr(device) == "Device('507f1f77bcf86cd799439011')"


class TestDeviceRequests:
    def test_list_request(self) -> None:
        req = DeviceListRequest()
        assert req.method == 'GET'
        assert req.full_path('default', False) == '/api/s/default/stat/device'

    def test_restart_request(self) -> None:
        req = DeviceRestartRequest.create('AA:BB:CC:DD:EE:FF')
        assert req.method == 'POST'
        assert req.data is not None
        assert req.data['cmd'] == 'restart'
        assert req.data['mac'] == 'aa:bb:cc:dd:ee:ff'

    def test_locate_request_enable(self) -> None:
        req = DeviceLocateRequest.create('aa:bb:cc:dd:ee:ff', locate=True)
        assert req.data is not None
        assert req.data['cmd'] == 'set-locate'

    def test_locate_request_disable(self) -> None:
        req = DeviceLocateRequest.create('aa:bb:cc:dd:ee:ff', locate=False)
        assert req.data is not None
        assert req.data['cmd'] == 'unset-locate'

    def test_set_led_status(self) -> None:
        device = Device(SAMPLE_DEVICE)
        req = DeviceSetLedStatus.create(device, status='on', color='#FF0000', brightness=50)
        assert req.method == 'PUT'
        assert req.data is not None
        assert req.data['led_override'] == 'on'
        assert req.data['led_override_color'] == '#FF0000'
        assert req.data['led_override_color_brightness'] == 50
        assert device.id in req.path

    def test_set_led_status_no_color(self) -> None:
        device = Device(SAMPLE_DEVICE)
        req = DeviceSetLedStatus.create(device, status='off')
        assert req.data is not None
        assert req.data['led_override'] == 'off'
        assert 'led_override_color' not in req.data
