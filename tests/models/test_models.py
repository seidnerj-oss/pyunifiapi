"""Tests for remaining model classes (Wlan, Site, Port, Outlet, Voucher, etc.)."""

from __future__ import annotations

from pyunifiapi.models.dpi import DPIRestrictionApp, DPIRestrictionAppEnableRequest, DPIRestrictionGroup
from pyunifiapi.models.firewall import FirewallPolicy, FirewallZone
from pyunifiapi.models.outlet import Outlet
from pyunifiapi.models.port import Port
from pyunifiapi.models.port_forward import PortForward, PortForwardEnableRequest
from pyunifiapi.models.site import Site, SiteListRequest
from pyunifiapi.models.system_information import SystemInformation
from pyunifiapi.models.traffic_route import TrafficRoute
from pyunifiapi.models.traffic_rule import TrafficRule, TrafficRuleEnableRequest
from pyunifiapi.models.voucher import Voucher, VoucherCreateRequest, VoucherDeleteRequest
from pyunifiapi.models.wlan import Wlan, WlanChangePasswordRequest, WlanEnableRequest


class TestWlan:
    def test_properties(self) -> None:
        wlan = Wlan({'_id': 'wlan1', 'name': 'MyNetwork', 'enabled': True, 'security': 'wpapsk', 'x_passphrase': 'secret123', 'is_guest': False})
        assert wlan.id == 'wlan1'
        assert wlan.name == 'MyNetwork'
        assert wlan.enabled is True
        assert wlan.security == 'wpapsk'
        assert wlan.passphrase == 'secret123'
        assert wlan.is_guest is False

    def test_enable_request(self) -> None:
        wlan = Wlan({'_id': 'wlan1'})
        req = WlanEnableRequest.create(wlan, enabled=False)
        assert req.data is not None
        assert req.data['enabled'] is False
        assert 'wlan1' in req.path

    def test_change_password_request(self) -> None:
        wlan = Wlan({'_id': 'wlan1'})
        req = WlanChangePasswordRequest.create(wlan, 'newpass')
        assert req.data is not None
        assert req.data['x_passphrase'] == 'newpass'


class TestSite:
    def test_properties(self) -> None:
        site = Site({'_id': 'site1', 'name': 'default', 'desc': 'Default Site', 'role': 'admin', 'attr_no_delete': True})
        assert site.site_id == 'site1'
        assert site.name == 'default'
        assert site.description == 'Default Site'
        assert site.role == 'admin'
        assert site.no_delete is True

    def test_list_request_global(self) -> None:
        req = SiteListRequest()
        assert req.full_path('default', False) == '/api/self/sites'
        assert req.full_path('default', True) == '/proxy/network/api/self/sites'


class TestPort:
    def test_properties(self) -> None:
        port = Port({'port_idx': 1, 'name': 'LAN1', 'ifname': 'eth0', 'up': True, 'enable': True, 'poe_enable': True, 'poe_power': '12.5'})
        assert port.port_idx == 1
        assert port.name == 'LAN1'
        assert port.ifname == 'eth0'
        assert port.up is True
        assert port.enabled is True
        assert port.poe_enable is True
        assert port.poe_power == 12.5

    def test_empty_name_fallback(self) -> None:
        port = Port({'port_idx': 5, 'name': ''})
        assert port.name == 'Port 5'

    def test_with_device_mac(self) -> None:
        port = Port({'port_idx': 1})
        port_with_mac = port.with_device_mac('aa:bb:cc:dd:ee:ff')
        assert port_with_mac.port_id == 'aa:bb:cc:dd:ee:ff-1'


class TestOutlet:
    def test_properties(self) -> None:
        outlet = Outlet(
            {
                'name': 'Outlet 1',
                'index': 0,
                'outlet_caps': 3,
                'relay_state': True,
                'cycle_enabled': False,
                'outlet_voltage': '120.5',
                'outlet_power': '45.2',
            }
        )
        assert outlet.name == 'Outlet 1'
        assert outlet.index == 0
        assert outlet.has_relay is True
        assert outlet.has_metering is True
        assert outlet.relay_state is True
        assert outlet.cycle_enabled is False
        assert outlet.voltage == 120.5
        assert outlet.power == 45.2


class TestSystemInformation:
    def test_properties(self) -> None:
        sysinfo = SystemInformation(
            {
                'hostname': 'UDM-Pro',
                'version': '8.0.28',
                'uptime': 864000,
                'ubnt_device_type': 'UDMPRO',
                'update_available': True,
                'is_cloud_console': False,
                'ip_addrs': ['192.168.1.1'],
            }
        )
        assert sysinfo.hostname == 'UDM-Pro'
        assert sysinfo.version == '8.0.28'
        assert sysinfo.uptime == 864000
        assert sysinfo.device_type == 'UDMPRO'
        assert sysinfo.update_available is True
        assert sysinfo.is_cloud_console is False
        assert sysinfo.ip_address == ['192.168.1.1']


class TestVoucher:
    def test_properties(self) -> None:
        voucher = Voucher(
            {
                '_id': 'v1',
                'code': 'ABCDE12345',
                'quota': 0,
                'duration': 60,
                'used': 1,
                'create_time': 1700000000,
                'qos_overwrite': True,
                'qos_rate_max_down': 10000,
            }
        )
        assert voucher.id == 'v1'
        assert voucher.code == 'ABCDE-12345'
        assert voucher.quota == 0
        assert voucher.duration == 60
        assert voucher.used == 1
        assert voucher.qos_rate_max_down == 10000

    def test_code_short(self) -> None:
        voucher = Voucher({'code': 'SHORT'})
        assert voucher.code == 'SHORT'

    def test_create_request(self) -> None:
        req = VoucherCreateRequest.create(expire_number=24, expire_unit=60, number=5, note='Test')
        assert req.data is not None
        assert req.data['cmd'] == 'create-voucher'
        assert req.data['expire'] == 24
        assert req.data['expire_unit'] == 60
        assert req.data['n'] == 5
        assert req.data['note'] == 'Test'

    def test_delete_request(self) -> None:
        req = VoucherDeleteRequest.create('v1')
        assert req.data is not None
        assert req.data['cmd'] == 'delete-voucher'
        assert req.data['_id'] == 'v1'


class TestTrafficRule:
    def test_properties(self) -> None:
        rule = TrafficRule({'_id': 'tr1', 'description': 'Block TikTok', 'enabled': True, 'action': 'BLOCK', 'matching_target': 'DOMAIN'})
        assert rule.id == 'tr1'
        assert rule.description == 'Block TikTok'
        assert rule.enabled is True
        assert rule.action == 'BLOCK'

    def test_enable_request(self) -> None:
        rule = TrafficRule({'_id': 'tr1', 'enabled': True})
        req = TrafficRuleEnableRequest.create(rule, enabled=False)
        assert req.data is not None
        assert req.data['enabled'] is False


class TestTrafficRoute:
    def test_properties(self) -> None:
        route = TrafficRoute({'_id': 'rt1', 'description': 'VPN route', 'enabled': True, 'matching_target': 'IP', 'next_hop': '10.0.0.1'})
        assert route.id == 'rt1'
        assert route.next_hop == '10.0.0.1'


class TestPortForward:
    def test_properties(self) -> None:
        pf = PortForward(
            {'_id': 'pf1', 'name': 'Web Server', 'enabled': True, 'dst_port': '80', 'fwd': '192.168.1.100', 'fwd_port': '8080', 'proto': 'tcp_udp'}
        )
        assert pf.id == 'pf1'
        assert pf.name == 'Web Server'
        assert pf.enabled is True
        assert pf.destination_port == '80'
        assert pf.forward_ip == '192.168.1.100'
        assert pf.forward_port == '8080'

    def test_enable_request(self) -> None:
        pf = PortForward({'_id': 'pf1'})
        req = PortForwardEnableRequest.create(pf, enabled=False)
        assert req.data is not None
        assert req.data['enabled'] is False
        assert 'pf1' in req.path


class TestFirewallZone:
    def test_properties(self) -> None:
        zone = FirewallZone({'_id': 'fz1', 'name': 'Internal', 'zone_key': 'internal', 'default_zone': True, 'network_ids': ['net1', 'net2']})
        assert zone.id == 'fz1'
        assert zone.name == 'Internal'
        assert zone.default_zone is True
        assert zone.network_ids == ['net1', 'net2']


class TestFirewallPolicy:
    def test_properties(self) -> None:
        policy = FirewallPolicy(
            {'_id': 'fp1', 'name': 'Allow IoT', 'enabled': True, 'action': 'ACCEPT', 'protocol': 'all', 'logging': True, 'index': 5}
        )
        assert policy.id == 'fp1'
        assert policy.name == 'Allow IoT'
        assert policy.action == 'ACCEPT'
        assert policy.logging is True
        assert policy.index == 5


class TestDPIRestrictionApp:
    def test_properties(self) -> None:
        app = DPIRestrictionApp({'_id': 'dpi1', 'apps': ['Netflix'], 'cats': ['Streaming'], 'blocked': True, 'enabled': True, 'log': False})
        assert app.id == 'dpi1'
        assert app.apps == ['Netflix']
        assert app.blocked is True
        assert app.enabled is True

    def test_enable_request(self) -> None:
        app = DPIRestrictionApp({'_id': 'dpi1'})
        req = DPIRestrictionAppEnableRequest.create(app, enabled=False)
        assert req.data is not None
        assert req.data['enabled'] is False


class TestDPIRestrictionGroup:
    def test_properties(self) -> None:
        group = DPIRestrictionGroup({'_id': 'dg1', 'name': 'Streaming', 'dpiapp_ids': ['dpi1', 'dpi2']})
        assert group.id == 'dg1'
        assert group.name == 'Streaming'
        assert group.dpiapp_ids == ['dpi1', 'dpi2']
