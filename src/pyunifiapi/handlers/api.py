"""Base handler for managing collections of typed API items."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from enum import StrEnum

from pyunifiapi.models.api import ApiItem

SubscriptionCallback = Callable[['ItemEvent', str, 'ApiItem'], None]
UnsubscribeFn = Callable[[], None]


class ItemEvent(StrEnum):
    """Events emitted when items in a handler's collection change."""

    ADDED = 'added'
    CHANGED = 'changed'
    DELETED = 'deleted'


class APIHandler[T: ApiItem]:
    """Base handler managing a keyed collection of typed API items.

    Subclasses specify:
    - ``item_cls``: the ApiItem subclass to instantiate from raw dicts
    - ``id_field``: the raw dict key used as the collection key (default ``_id``)

    The handler provides dict-like read access and processes raw data from
    API responses or WebSocket messages, emitting ``ItemEvent`` callbacks
    when items are added, changed, or deleted.
    """

    item_cls: type[T]
    id_field: str = '_id'

    def __init__(self) -> None:
        self._items: dict[str, T] = {}
        self._subscribers: dict[int, SubscriptionCallback] = {}
        self._sub_id = 0

    # --- Dict-like read interface ---

    def __getitem__(self, key: str) -> T:
        return self._items[key]

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def get(self, key: str, default: T | None = None) -> T | None:
        return self._items.get(key, default)

    def keys(self) -> Iterator[str]:
        return iter(self._items.keys())

    def values(self) -> Iterator[T]:
        return iter(self._items.values())

    def items(self) -> Iterator[tuple[str, T]]:
        return iter(self._items.items())

    # --- Subscription ---

    def subscribe(self, callback: SubscriptionCallback) -> UnsubscribeFn:
        """Register a callback for item events. Returns an unsubscribe function."""
        self._sub_id += 1
        sub_id = self._sub_id
        self._subscribers[sub_id] = callback

        def unsubscribe() -> None:
            self._subscribers.pop(sub_id, None)

        return unsubscribe

    def _notify(self, event: ItemEvent, item_id: str, item: T) -> None:
        for callback in list(self._subscribers.values()):
            callback(event, item_id, item)

    # --- Data processing ---

    def _extract_key(self, raw: dict) -> str | None:
        """Extract the collection key from a raw dict. Returns None if missing."""
        key = raw.get(self.id_field)
        return str(key) if key is not None else None

    def process_raw(self, items: list[dict]) -> None:
        """Process a list of raw dicts, updating the collection.

        For each item:
        - If the key is new, create the item and emit ADDED
        - If the key exists, update the item's raw data and emit CHANGED
        """
        for raw in items:
            key = self._extract_key(raw)
            if key is None:
                continue
            existing = self._items.get(key)
            if existing is None:
                item = self.item_cls(raw)
                self._items[key] = item
                self._notify(ItemEvent.ADDED, key, item)
            else:
                existing.raw.update(raw)
                self._notify(ItemEvent.CHANGED, key, existing)

    def process_full(self, items: list[dict]) -> None:
        """Replace the entire collection from a full API response.

        Emits ADDED for new items, CHANGED for updated items, and
        DELETED for items no longer present.
        """
        seen_keys: set[str] = set()
        for raw in items:
            key = self._extract_key(raw)
            if key is None:
                continue
            seen_keys.add(key)
            existing = self._items.get(key)
            if existing is None:
                item = self.item_cls(raw)
                self._items[key] = item
                self._notify(ItemEvent.ADDED, key, item)
            else:
                existing.raw.update(raw)
                self._notify(ItemEvent.CHANGED, key, existing)

        for key in list(self._items.keys()):
            if key not in seen_keys:
                item = self._items.pop(key)
                self._notify(ItemEvent.DELETED, key, item)

    def remove(self, keys: list[str]) -> None:
        """Remove items by key, emitting DELETED for each."""
        for key in keys:
            item = self._items.pop(key, None)
            if item is not None:
                self._notify(ItemEvent.DELETED, key, item)

    def clear(self) -> None:
        """Remove all items, emitting DELETED for each."""
        for key, item in list(self._items.items()):
            self._notify(ItemEvent.DELETED, key, item)
        self._items.clear()
