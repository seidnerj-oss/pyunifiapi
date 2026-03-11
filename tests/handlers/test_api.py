"""Tests for the APIHandler base class."""

from __future__ import annotations

from typing import final

from pyunifiapi.handlers.api import APIHandler, ItemEvent
from pyunifiapi.models.api import ApiItem


@final
class DummyItem(ApiItem):
    @property
    def id(self) -> str:
        return self.raw.get('_id', '')

    @property
    def name(self) -> str:
        return self.raw.get('name', '')


class DummyHandler(APIHandler[DummyItem]):
    item_cls = DummyItem


class TestDictInterface:
    def test_empty(self) -> None:
        h = DummyHandler()
        assert len(h) == 0
        assert list(h) == []
        assert 'x' not in h

    def test_getitem_after_process(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a', 'name': 'Alpha'}])
        assert h['a'].name == 'Alpha'

    def test_contains(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}])
        assert 'a' in h
        assert 'b' not in h

    def test_iter_keys_values_items(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}])
        assert set(h) == {'a', 'b'}
        assert set(h.keys()) == {'a', 'b'}
        assert len(list(h.values())) == 2
        assert {k for k, _ in h.items()} == {'a', 'b'}

    def test_len(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}, {'_id': 'c'}])
        assert len(h) == 3

    def test_get_existing(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a', 'name': 'Alpha'}])
        item = h.get('a')
        assert item is not None
        assert item.name == 'Alpha'

    def test_get_missing(self) -> None:
        h = DummyHandler()
        assert h.get('missing') is None

    def test_getitem_missing_raises(self) -> None:
        h = DummyHandler()
        try:
            h['missing']
            assert False, 'Expected KeyError'
        except KeyError:
            pass


class TestProcessRaw:
    def test_add_new_items(self) -> None:
        h = DummyHandler()
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}])
        assert len(h) == 2
        assert events == [(ItemEvent.ADDED, 'a'), (ItemEvent.ADDED, 'b')]

    def test_update_existing_items(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a', 'name': 'Old'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.process_raw([{'_id': 'a', 'name': 'New'}])
        assert h['a'].name == 'New'
        assert events == [(ItemEvent.CHANGED, 'a')]

    def test_skip_items_without_key(self) -> None:
        h = DummyHandler()
        h.process_raw([{'name': 'no id'}])
        assert len(h) == 0

    def test_mixed_add_and_update(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a', 'name': 'Alpha'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.process_raw([{'_id': 'a', 'name': 'Updated'}, {'_id': 'b', 'name': 'New'}])
        assert len(h) == 2
        assert events == [(ItemEvent.CHANGED, 'a'), (ItemEvent.ADDED, 'b')]


class TestProcessFull:
    def test_adds_and_removes(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.process_full([{'_id': 'b', 'name': 'Updated'}, {'_id': 'c'}])
        assert 'a' not in h
        assert 'b' in h
        assert 'c' in h
        assert (ItemEvent.CHANGED, 'b') in events
        assert (ItemEvent.ADDED, 'c') in events
        assert (ItemEvent.DELETED, 'a') in events

    def test_full_replace_empty(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.process_full([])
        assert len(h) == 0
        assert (ItemEvent.DELETED, 'a') in events
        assert (ItemEvent.DELETED, 'b') in events


class TestRemove:
    def test_remove_existing(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.remove(['a'])
        assert 'a' not in h
        assert len(h) == 1
        assert events == [(ItemEvent.DELETED, 'a')]

    def test_remove_nonexistent(self) -> None:
        h = DummyHandler()
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.remove(['missing'])
        assert events == []


class TestClear:
    def test_clear_all(self) -> None:
        h = DummyHandler()
        h.process_raw([{'_id': 'a'}, {'_id': 'b'}, {'_id': 'c'}])
        events: list[tuple[ItemEvent, str]] = []
        h.subscribe(lambda ev, key, _item: events.append((ev, key)))
        h.clear()
        assert len(h) == 0
        assert len(events) == 3
        assert all(ev == ItemEvent.DELETED for ev, _ in events)


class TestSubscription:
    def test_subscribe_and_unsubscribe(self) -> None:
        h = DummyHandler()
        events: list[str] = []
        unsub = h.subscribe(lambda ev, key, _item: events.append(key))
        h.process_raw([{'_id': 'a'}])
        assert events == ['a']
        unsub()
        h.process_raw([{'_id': 'b'}])
        assert events == ['a']  # no new events after unsub

    def test_multiple_subscribers(self) -> None:
        h = DummyHandler()
        events1: list[str] = []
        events2: list[str] = []
        h.subscribe(lambda ev, key, _item: events1.append(key))
        h.subscribe(lambda ev, key, _item: events2.append(key))
        h.process_raw([{'_id': 'a'}])
        assert events1 == ['a']
        assert events2 == ['a']

    def test_callback_receives_item(self) -> None:
        h = DummyHandler()
        received: list[DummyItem] = []
        h.subscribe(lambda ev, key, item: received.append(item))  # type: ignore[arg-type]
        h.process_raw([{'_id': 'a', 'name': 'Alpha'}])
        assert len(received) == 1
        assert received[0].name == 'Alpha'


class TestCustomIdField:
    def test_mac_as_id_field(self) -> None:
        class MacHandler(APIHandler[DummyItem]):
            item_cls = DummyItem
            id_field = 'mac'

        h = MacHandler()
        h.process_raw([{'mac': 'aa:bb:cc:dd:ee:ff', 'name': 'Device'}])
        assert 'aa:bb:cc:dd:ee:ff' in h
        assert h['aa:bb:cc:dd:ee:ff'].name == 'Device'
