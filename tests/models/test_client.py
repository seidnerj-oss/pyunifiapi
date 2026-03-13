"""Tests for Client model and request classes."""

from __future__ import annotations

from pyunifiapi.models.client import (
    AllClientListRequest,
    Client,
    ClientBlockRequest,
    ClientListRequest,
    ClientReconnectRequest,
    ClientRemoveRequest,
    ClientUnblockRequest,
)

SAMPLE_CLIENT = {
    '_id': '507f1f77bcf86cd799439022',
    'mac': '11:22:33:44:55:66',
    'name': 'iPhone',
    'hostname': 'iphone-user',
    'oui': 'Apple',
    'site_id': '5a32aa4ee4b0412345678901',
    'ip': '192.168.1.50',
    'network': 'LAN',
    'network_id': 'net123',
    'vlan': 0,
    'is_wired': False,
    'is_guest': False,
    'authorized': True,
    'blocked': False,
    'ap_mac': 'aa:bb:cc:dd:ee:ff',
    'essid': 'MyNetwork',
    'channel': 36,
    'radio': 'na',
    'signal': -55,
    'rssi': 40,
    'satisfaction': 95,
    'tx_rate': 866000,
    'rx_rate': 433000,
    'uptime': 3600,
    'rx_bytes': 1000000,
    'tx_bytes': 500000,
    'first_seen': 1700000000,
    'last_seen': 1700003600,
}


class TestClient:
    def test_identity(self) -> None:
        client = Client(SAMPLE_CLIENT)
        assert client.id == '507f1f77bcf86cd799439022'
        assert client.mac == '11:22:33:44:55:66'
        assert client.name == 'iPhone'
        assert client.hostname == 'iphone-user'
        assert client.oui == 'Apple'

    def test_network(self) -> None:
        client = Client(SAMPLE_CLIENT)
        assert client.ip == '192.168.1.50'
        assert client.network == 'LAN'
        assert client.vlan == 0

    def test_connection_type(self) -> None:
        client = Client(SAMPLE_CLIENT)
        assert client.is_wired is False
        assert client.is_guest is False
        assert client.is_authorized is True
        assert client.blocked is False

    def test_wireless(self) -> None:
        client = Client(SAMPLE_CLIENT)
        assert client.essid == 'MyNetwork'
        assert client.channel == 36
        assert client.radio == 'na'
        assert client.signal == -55
        assert client.rssi == 40
        assert client.tx_rate == 866000

    def test_statistics(self) -> None:
        client = Client(SAMPLE_CLIENT)
        assert client.uptime == 3600
        assert client.rx_bytes == 1000000
        assert client.tx_bytes == 500000

    def test_name_fallback_to_hostname(self) -> None:
        client = Client({'hostname': 'laptop', 'mac': '00:11:22:33:44:55'})
        assert client.name == 'laptop'

    def test_name_fallback_to_mac(self) -> None:
        client = Client({'mac': '00:11:22:33:44:55'})
        assert client.name == '00:11:22:33:44:55'

    def test_defaults(self) -> None:
        client = Client({})
        assert client.mac == ''
        assert client.ip == ''
        assert client.is_wired is False
        assert client.blocked is False
        assert client.uptime == 0


class TestClientRequests:
    def test_list_request(self) -> None:
        req = ClientListRequest()
        assert req.full_path('default', False) == '/api/s/default/stat/sta'

    def test_all_list_request(self) -> None:
        req = AllClientListRequest()
        assert req.full_path('default', False) == '/api/s/default/stat/alluser'

    def test_block_request(self) -> None:
        req = ClientBlockRequest.create('11:22:33:44:55:66')
        assert req.data is not None
        assert req.data['cmd'] == 'block-sta'
        assert req.data['mac'] == '11:22:33:44:55:66'

    def test_unblock_request(self) -> None:
        req = ClientUnblockRequest.create('11:22:33:44:55:66')
        assert req.data is not None
        assert req.data['cmd'] == 'unblock-sta'

    def test_reconnect_request(self) -> None:
        req = ClientReconnectRequest.create('11:22:33:44:55:66')
        assert req.data is not None
        assert req.data['cmd'] == 'kick-sta'

    def test_remove_request(self) -> None:
        req = ClientRemoveRequest.create(['11:22:33:44:55:66', 'AA:BB:CC:DD:EE:FF'])
        assert req.data is not None
        assert req.data['cmd'] == 'forget-sta'
        assert req.data['macs'] == ['11:22:33:44:55:66', 'aa:bb:cc:dd:ee:ff']
