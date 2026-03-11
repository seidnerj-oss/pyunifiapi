"""Tests for Message model and MessageKey enum."""

from __future__ import annotations

from pyunifiapi.models.message import Message, MessageKey, MessageMeta


class TestMessageKey:
    def test_known_keys(self) -> None:
        assert MessageKey.CLIENT == 'sta:sync'
        assert MessageKey.DEVICE == 'device:sync'
        assert MessageKey.EVENT == 'events'
        assert MessageKey.WLAN_CONF_UPDATED == 'wlanconf:sync'

    def test_string_comparison(self) -> None:
        assert MessageKey.CLIENT == 'sta:sync'
        assert 'sta:sync' == MessageKey.CLIENT


class TestMessageMeta:
    def test_from_raw(self) -> None:
        meta = MessageMeta.from_raw({'rc': 'ok', 'message': 'device:sync', 'data': {'key': 'val'}})
        assert meta.rc == 'ok'
        assert meta.message_key == 'device:sync'
        assert meta.data == {'key': 'val'}

    def test_from_raw_defaults(self) -> None:
        meta = MessageMeta.from_raw({})
        assert meta.rc == ''
        assert meta.message_key == ''


class TestMessage:
    def test_from_raw_list(self) -> None:
        msg = Message.from_raw(
            {
                'meta': {'rc': 'ok', 'message': 'sta:sync'},
                'data': [{'mac': 'aa:bb:cc:dd:ee:ff'}],
            }
        )
        assert msg.meta.message_key == 'sta:sync'
        assert len(msg.data) == 1
        assert msg.data[0]['mac'] == 'aa:bb:cc:dd:ee:ff'

    def test_from_raw_dict_wrapped(self) -> None:
        msg = Message.from_raw(
            {
                'meta': {'rc': 'ok', 'message': 'device:sync'},
                'data': {'mac': '11:22:33:44:55:66'},
            }
        )
        assert len(msg.data) == 1
        assert msg.data[0]['mac'] == '11:22:33:44:55:66'

    def test_from_raw_empty(self) -> None:
        msg = Message.from_raw({})
        assert msg.data == []
