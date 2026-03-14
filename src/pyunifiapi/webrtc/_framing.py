"""Binme framing protocol for cloud API data channel.

The binme protocol is a streaming binary format. Data arrives in arbitrary
chunks across data channel messages. Each logical message consists of two
parts (header + body), each with an 8-byte part header:

    Part header (8 bytes):
        Byte 0:    type (1=HEADER, 2=BODY)
        Byte 1:    format (1=JSON, 2=STRING, 3=BINARY)
        Byte 2:    compressed (0 or 1, zlib deflate)
        Byte 3:    reserved (0)
        Bytes 4-7: data length (uint32 BE)

    Followed by `length` bytes of data.

API requests use:
    Header: {"id":"<uuid>","type":"httpRequest","path":"/api/...","method":"GET","headers":{...}}
    Body: request payload (empty for GET)

API responses use:
    Header: {"id":"<uuid>","type":"httpResponse","statusCode":200,...}
    Body: response payload (JSON)
"""

from __future__ import annotations

import json
import struct
import uuid as uuid_mod
import zlib
from dataclasses import dataclass, field

TYPE_HEADER = 1
TYPE_BODY = 2
FORMAT_JSON = 1
FORMAT_STRING = 2
FORMAT_BINARY = 3

PART_HDR_SIZE = 8


@dataclass
class FramedMessage:
    """A decoded binme message."""

    header: dict = field(default_factory=dict)
    body: bytes = b''

    @property
    def request_id(self) -> str:
        return self.header.get('id', '')


def _compress(data: bytes) -> bytes:
    return zlib.compress(data)


def encode_frame(message_id: int, metadata: dict, payload: bytes = b'') -> tuple[bytes, str]:
    """Encode an API request in binme format.

    Returns (frame_bytes, request_id).
    """
    request_id = str(uuid_mod.uuid4())

    header_obj = {
        'id': request_id,
        'type': 'httpRequest',
        'path': metadata.get('path', '/'),
        'method': metadata.get('method', 'GET'),
        'headers': metadata.get('headers', {'content-length': len(payload)}),
    }

    header_json = json.dumps(header_obj).encode('utf-8')
    header_compressed = _compress(header_json)

    body_data = payload or b''
    body_compressed = _compress(body_data)

    result = bytearray()

    result.append(TYPE_HEADER)
    result.append(FORMAT_JSON)
    result.append(1)
    result.append(0)
    result.extend(struct.pack('>I', len(header_compressed)))
    result.extend(header_compressed)

    result.append(TYPE_BODY)
    result.append(FORMAT_BINARY)
    result.append(1)
    result.append(0)
    result.extend(struct.pack('>I', len(body_compressed)))
    result.extend(body_compressed)

    return bytes(result), request_id


class BinmeStreamParser:
    """Streaming binme parser that accumulates bytes across data channel messages.

    Feeds raw bytes and emits complete FramedMessage objects.
    Handles the case where a single binme frame spans multiple DC messages.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._header: dict = {}
        self._header_done = False
        self._body: bytes = b''
        self._body_done = False
        self._current_part_type: int = 0
        self._current_part_fmt: int = 0
        self._current_part_compressed: bool = False
        self._current_part_len: int = 0
        self._current_part_data = bytearray()
        self._reading_part_header = True
        self._parts_completed = 0

    def feed(self, data: bytes) -> list[FramedMessage]:
        """Feed raw bytes and return any complete messages."""
        self._buffer.extend(data)
        results = []

        while self._buffer:
            if self._reading_part_header:
                if len(self._buffer) < PART_HDR_SIZE:
                    break
                self._current_part_type = self._buffer[0]
                self._current_part_fmt = self._buffer[1]
                self._current_part_compressed = self._buffer[2] != 0
                self._current_part_len = struct.unpack('>I', self._buffer[4:8])[0]
                self._current_part_data = bytearray()
                self._buffer = self._buffer[PART_HDR_SIZE:]
                self._reading_part_header = False

            needed = self._current_part_len - len(self._current_part_data)
            available = min(needed, len(self._buffer))
            self._current_part_data.extend(self._buffer[:available])
            self._buffer = self._buffer[available:]

            if len(self._current_part_data) >= self._current_part_len:
                part_bytes = bytes(self._current_part_data)
                if self._current_part_compressed and part_bytes:
                    part_bytes = zlib.decompress(part_bytes)

                if self._current_part_type == TYPE_HEADER:
                    if self._current_part_fmt == FORMAT_JSON and part_bytes:
                        self._header = json.loads(part_bytes.decode('utf-8'))
                    self._header_done = True
                elif self._current_part_type == TYPE_BODY:
                    self._body = part_bytes
                    self._body_done = True

                self._parts_completed += 1
                self._reading_part_header = True

                if self._header_done and self._body_done:
                    results.append(FramedMessage(header=self._header, body=self._body))
                    self._header = {}
                    self._body = b''
                    self._header_done = False
                    self._body_done = False
                    self._parts_completed = 0

        return results


def decode_response(data: bytes) -> FramedMessage:
    """Decode a complete binme message (convenience for single-message frames)."""
    parser = BinmeStreamParser()
    results = parser.feed(data)
    if results:
        return results[0]
    return FramedMessage()
