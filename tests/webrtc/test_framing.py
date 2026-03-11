"""Tests for binary message framing protocol."""

from __future__ import annotations

import json

import pytest

from pyunifiapi.webrtc._framing import FrameBuffer, decode_frame, encode_frame


class TestEncodeFrame:
    def test_encode_basic(self) -> None:
        metadata = {'path': '/api/test', 'method': 'GET'}
        frame = encode_frame(1, metadata)

        assert isinstance(frame, bytes)
        assert len(frame) > 16  # At least header + some JSON

    def test_encode_with_payload(self) -> None:
        metadata = {'path': '/api/test', 'method': 'POST'}
        payload = b'{"key": "value"}'
        frame = encode_frame(42, metadata, payload)

        assert isinstance(frame, bytes)
        assert len(frame) > 16 + len(payload)

    def test_encode_empty_metadata(self) -> None:
        frame = encode_frame(1, {})
        assert isinstance(frame, bytes)


class TestDecodeFrame:
    def test_roundtrip(self) -> None:
        metadata = {'path': '/api/s/default/stat/device', 'method': 'GET', 'contentType': 'application/json'}
        payload = b'{"data": []}'
        frame = encode_frame(123, metadata, payload)
        decoded = decode_frame(frame)

        assert decoded.message_id == 123
        assert decoded.metadata == metadata
        assert decoded.payload == payload

    def test_roundtrip_no_payload(self) -> None:
        metadata = {'path': '/api/test'}
        frame = encode_frame(1, metadata)
        decoded = decode_frame(frame)

        assert decoded.message_id == 1
        assert decoded.metadata == metadata
        assert decoded.payload == b''

    def test_roundtrip_large_message_id(self) -> None:
        metadata = {'test': True}
        frame = encode_frame(2**32 + 1, metadata)
        decoded = decode_frame(frame)
        assert decoded.message_id == 2**32 + 1

    def test_decode_too_short(self) -> None:
        with pytest.raises(ValueError, match='too short'):
            decode_frame(b'\x00\x00')

    def test_decode_truncated(self) -> None:
        metadata = {'path': '/api/test'}
        frame = encode_frame(1, metadata)
        # Truncate after the header but before the JSON payload is complete
        with pytest.raises(ValueError, match='truncated'):
            decode_frame(frame[:20])


class TestFrameBuffer:
    def test_single_complete_frame(self) -> None:
        metadata = {'path': '/api/test'}
        frame = encode_frame(1, metadata)

        buf = FrameBuffer()
        frames = buf.feed(frame)

        assert len(frames) == 1
        assert frames[0].message_id == 1
        assert frames[0].metadata == metadata

    def test_multiple_frames_at_once(self) -> None:
        frame1 = encode_frame(1, {'path': '/first'})
        frame2 = encode_frame(2, {'path': '/second'})

        buf = FrameBuffer()
        frames = buf.feed(frame1 + frame2)

        assert len(frames) == 2
        assert frames[0].message_id == 1
        assert frames[1].message_id == 2

    def test_partial_frame(self) -> None:
        frame = encode_frame(1, {'path': '/api/test'}, b'payload-data')

        buf = FrameBuffer()

        # Feed first half
        mid = len(frame) // 2
        frames = buf.feed(frame[:mid])
        assert len(frames) == 0  # Incomplete

        # Feed second half
        frames = buf.feed(frame[mid:])
        assert len(frames) == 1
        assert frames[0].message_id == 1

    def test_byte_by_byte(self) -> None:
        frame = encode_frame(1, {'test': True})

        buf = FrameBuffer()
        frames = []
        for byte in frame:
            frames.extend(buf.feed(bytes([byte])))

        assert len(frames) == 1
        assert frames[0].message_id == 1

    def test_empty_feed(self) -> None:
        buf = FrameBuffer()
        assert buf.feed(b'') == []

    def test_frame_with_payload_roundtrip(self) -> None:
        metadata = {'contentType': 'application/json'}
        payload = json.dumps({'data': [{'mac': 'aa:bb:cc:dd:ee:ff'}]}).encode('utf-8')

        frame = encode_frame(99, metadata, payload)
        buf = FrameBuffer()
        frames = buf.feed(frame)

        assert len(frames) == 1
        assert frames[0].message_id == 99
        assert json.loads(frames[0].payload) == {'data': [{'mac': 'aa:bb:cc:dd:ee:ff'}]}
