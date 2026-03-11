"""Tests for API base classes."""

from __future__ import annotations

import pytest

from pyunifiapi.models.api import ApiItem, ApiRequest, ApiRequestV2, TypedApiResponse


class ConcreteItem(ApiItem):
    """Concrete subclass for testing."""

    @property
    def name(self) -> str:
        return self.raw.get('name', '')


class TestApiItem:
    def test_raw_storage(self) -> None:
        item = ConcreteItem({'name': 'test', '_id': '123'})
        assert item.raw == {'name': 'test', '_id': '123'}

    def test_repr_with_id(self) -> None:
        item = ConcreteItem({'_id': 'abc123'})
        assert repr(item) == "ConcreteItem('abc123')"

    def test_repr_with_mac(self) -> None:
        item = ConcreteItem({'mac': 'aa:bb:cc:dd:ee:ff'})
        assert repr(item) == "ConcreteItem('aa:bb:cc:dd:ee:ff')"

    def test_repr_empty(self) -> None:
        item = ConcreteItem({})
        assert repr(item) == "ConcreteItem('')"

    def test_property_access(self) -> None:
        item = ConcreteItem({'name': 'my-device'})
        assert item.name == 'my-device'

    def test_property_default(self) -> None:
        item = ConcreteItem({})
        assert item.name == ''


class TestApiRequest:
    def test_full_path_classic(self) -> None:
        req = ApiRequest(method='GET', path='/api/s/{site}/stat/device')
        assert req.full_path('default', is_unifi_os=False) == '/api/s/default/stat/device'

    def test_full_path_unifi_os(self) -> None:
        req = ApiRequest(method='GET', path='/api/s/{site}/stat/device')
        assert req.full_path('default', is_unifi_os=True) == '/proxy/network/api/s/default/stat/device'

    def test_full_path_custom_site(self) -> None:
        req = ApiRequest(method='GET', path='/api/s/{site}/stat/sta')
        assert req.full_path('office', is_unifi_os=False) == '/api/s/office/stat/sta'

    def test_data_field(self) -> None:
        req = ApiRequest(method='POST', path='/api/s/{site}/cmd/devmgr', data={'cmd': 'restart'})
        assert req.data == {'cmd': 'restart'}

    def test_frozen(self) -> None:
        req = ApiRequest(method='GET', path='/test')
        with pytest.raises(AttributeError):
            req.method = 'POST'  # type: ignore[misc]


class TestApiRequestV2:
    def test_full_path_classic(self) -> None:
        req = ApiRequestV2(method='GET', path='/trafficrules')
        assert req.full_path('default', is_unifi_os=False) == '/v2/api/site/default/trafficrules'

    def test_full_path_unifi_os(self) -> None:
        req = ApiRequestV2(method='GET', path='/trafficrules')
        assert req.full_path('default', is_unifi_os=True) == '/proxy/network/v2/api/site/default/trafficrules'


class TestTypedApiResponse:
    def test_from_raw_success(self) -> None:
        resp = TypedApiResponse.from_raw({'meta': {'rc': 'ok'}, 'data': [{'name': 'test'}]})
        assert resp.ok is True
        assert resp.data == [{'name': 'test'}]

    def test_from_raw_error(self) -> None:
        resp = TypedApiResponse.from_raw({'meta': {'rc': 'error', 'msg': 'api.err.Invalid'}, 'data': []})
        assert resp.ok is False

    def test_from_raw_empty(self) -> None:
        resp = TypedApiResponse.from_raw({})
        assert resp.ok is False
        assert resp.data == []
