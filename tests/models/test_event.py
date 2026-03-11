"""Tests for Event model and EventKey enum."""

from __future__ import annotations

from pyunifiapi.models.event import Event, EventKey

SAMPLE_EVENT = {
    '_id': 'evt123',
    'key': 'EVT_WU_Connected',
    'msg': 'User[aa:bb:cc:dd:ee:ff] has connected to AP[Living Room]',
    'datetime': '2024-01-15T10:30:00Z',
    'time': 1705312200,
    'site_id': 'site123',
    'subsystem': 'wlan',
    'user': 'aa:bb:cc:dd:ee:ff',
    'ap': '11:22:33:44:55:66',
    'hostname': 'iPhone',
    'ssid': 'MyNetwork',
    'channel': 36,
    'radio': 'na',
    'duration': 0,
}


class TestEventKey:
    def test_wireless_client_connected(self) -> None:
        assert EventKey.WIRELESS_CLIENT_CONNECTED == 'EVT_WU_Connected'

    def test_ap_lost_contact(self) -> None:
        assert EventKey.AP_LOST_CONTACT == 'EVT_AP_Lost_Contact'


class TestEvent:
    def test_identity(self) -> None:
        event = Event(SAMPLE_EVENT)
        assert event.id == 'evt123'
        assert event.key == 'EVT_WU_Connected'
        assert event.msg.startswith('User[')

    def test_event_key_parsing(self) -> None:
        event = Event(SAMPLE_EVENT)
        assert event.event_key == EventKey.WIRELESS_CLIENT_CONNECTED

    def test_event_key_unknown(self) -> None:
        event = Event({'key': 'EVT_UNKNOWN_SomethingNew'})
        assert event.event_key is None

    def test_timing(self) -> None:
        event = Event(SAMPLE_EVENT)
        assert event.datetime == '2024-01-15T10:30:00Z'
        assert event.time == 1705312200

    def test_wireless_fields(self) -> None:
        event = Event(SAMPLE_EVENT)
        assert event.ssid == 'MyNetwork'
        assert event.channel == 36
        assert event.radio == 'na'
        assert event.hostname == 'iPhone'

    def test_mac_from_user(self) -> None:
        event = Event(SAMPLE_EVENT)
        assert event.mac == 'aa:bb:cc:dd:ee:ff'

    def test_mac_fallback_chain(self) -> None:
        event = Event({'sw': '33:44:55:66:77:88'})
        assert event.device == '33:44:55:66:77:88'

    def test_defaults(self) -> None:
        event = Event({})
        assert event.id == ''
        assert event.key == ''
        assert event.mac == ''
        assert event.duration == 0
