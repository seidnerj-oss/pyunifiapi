"""Tests for binme binary framing protocol."""

from __future__ import annotations

import json

from pyunifiapi.webrtc._framing import BinmeStreamParser, FramedMessage, decode_response, encode_frame


class TestEncodeFrame:
    def test_encode_basic(self) -> None:
        metadata = {'path': '/api/test', 'method': 'GET'}
        frame_bytes, request_id = encode_frame(1, metadata)

        assert isinstance(frame_bytes, bytes)
        assert len(frame_bytes) > 16
        assert isinstance(request_id, str)
        assert len(request_id) == 36  # UUID format

    def test_encode_with_payload(self) -> None:
        metadata = {'path': '/api/test', 'method': 'POST'}
        payload = b'{"key": "value"}'
        frame_bytes, request_id = encode_frame(42, metadata, payload)

        assert isinstance(frame_bytes, bytes)
        assert isinstance(request_id, str)

    def test_encode_empty_metadata(self) -> None:
        frame_bytes, request_id = encode_frame(1, {})
        assert isinstance(frame_bytes, bytes)
        assert isinstance(request_id, str)

    def test_unique_request_ids(self) -> None:
        _, id1 = encode_frame(1, {'path': '/a'})
        _, id2 = encode_frame(2, {'path': '/b'})
        assert id1 != id2


class TestDecodeResponse:
    def test_roundtrip(self) -> None:
        metadata = {'path': '/api/s/default/stat/device', 'method': 'GET'}
        frame_bytes, request_id = encode_frame(123, metadata)

        decoded = decode_response(frame_bytes)
        assert decoded.request_id == request_id
        assert decoded.header['type'] == 'httpRequest'
        assert decoded.header['path'] == '/api/s/default/stat/device'
        assert decoded.header['method'] == 'GET'

    def test_roundtrip_with_payload(self) -> None:
        metadata = {'path': '/api/test', 'method': 'POST'}
        payload = b'{"data": []}'
        frame_bytes, request_id = encode_frame(1, metadata, payload)

        decoded = decode_response(frame_bytes)
        assert decoded.request_id == request_id

    def test_empty_data(self) -> None:
        decoded = decode_response(b'')
        assert decoded.header == {}
        assert decoded.body == b''


class TestBinmeStreamParser:
    def test_single_complete_frame(self) -> None:
        metadata = {'path': '/api/test', 'method': 'GET'}
        frame_bytes, request_id = encode_frame(1, metadata)

        parser = BinmeStreamParser()
        frames = parser.feed(frame_bytes)

        assert len(frames) == 1
        assert frames[0].request_id == request_id

    def test_multiple_frames_at_once(self) -> None:
        frame1, id1 = encode_frame(1, {'path': '/first', 'method': 'GET'})
        frame2, id2 = encode_frame(2, {'path': '/second', 'method': 'GET'})

        parser = BinmeStreamParser()
        frames = parser.feed(frame1 + frame2)

        assert len(frames) == 2
        assert frames[0].request_id == id1
        assert frames[1].request_id == id2

    def test_partial_frame(self) -> None:
        frame_bytes, request_id = encode_frame(1, {'path': '/api/test', 'method': 'GET'}, b'payload-data')

        parser = BinmeStreamParser()

        mid = len(frame_bytes) // 2
        frames = parser.feed(frame_bytes[:mid])
        assert len(frames) == 0

        frames = parser.feed(frame_bytes[mid:])
        assert len(frames) == 1
        assert frames[0].request_id == request_id

    def test_byte_by_byte(self) -> None:
        frame_bytes, request_id = encode_frame(1, {'path': '/test', 'method': 'GET'})

        parser = BinmeStreamParser()
        frames = []
        for byte in frame_bytes:
            frames.extend(parser.feed(bytes([byte])))

        assert len(frames) == 1
        assert frames[0].request_id == request_id

    def test_empty_feed(self) -> None:
        parser = BinmeStreamParser()
        assert parser.feed(b'') == []

    def test_frame_with_json_payload(self) -> None:
        metadata = {'path': '/api/devices', 'method': 'GET'}
        payload = json.dumps({'data': [{'mac': 'aa:bb:cc:dd:ee:ff'}]}).encode('utf-8')
        frame_bytes, request_id = encode_frame(99, metadata, payload)

        parser = BinmeStreamParser()
        frames = parser.feed(frame_bytes)

        assert len(frames) == 1
        assert frames[0].request_id == request_id


class TestFramedMessage:
    def test_request_id_property(self) -> None:
        msg = FramedMessage(header={'id': 'test-uuid-123'}, body=b'')
        assert msg.request_id == 'test-uuid-123'

    def test_empty_header(self) -> None:
        msg = FramedMessage()
        assert msg.request_id == ''
        assert msg.body == b''
