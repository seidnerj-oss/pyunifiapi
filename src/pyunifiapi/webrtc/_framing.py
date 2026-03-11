"""Binary message framing protocol for cloud API data channel.

Wire format (big-endian):
    Bytes 0-3:   Total length (uint32, excluding these 4 bytes)
    Bytes 4-11:  Message ID (uint64)
    Bytes 12-15: Request/response JSON length (uint32)
    Bytes 16-N:  JSON string (UTF-8)
    Bytes N-end: Data payload

This protocol is used to multiplex REST API requests/responses
over a single WebRTC data channel in cloud API mode.
"""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass, field

HEADER_FORMAT = '>IQI'  # total_len (uint32), msg_id (uint64), json_len (uint32)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 16 bytes
LENGTH_PREFIX_SIZE = 4  # The total_len field itself


@dataclass
class FramedMessage:
    """A decoded message from the data channel."""

    message_id: int
    metadata: dict = field(default_factory=dict)
    payload: bytes = b''


def encode_frame(message_id: int, metadata: dict, payload: bytes = b'') -> bytes:
    """Encode a framed message for the data channel.

    Args:
        message_id: Incrementing message ID for request/response matching.
        metadata: JSON-serializable dict (path, method, contentType, etc.).
        payload: Optional data payload (JSON string or binary).

    Returns:
        The encoded binary frame.
    """
    json_bytes = json.dumps(metadata).encode('utf-8')
    json_len = len(json_bytes)
    total_len = 8 + 4 + json_len + len(payload)  # msg_id + json_len_field + json + payload

    header = struct.pack('>I', total_len) + struct.pack('>QI', message_id, json_len)
    return header + json_bytes + payload


def decode_frame(data: bytes) -> FramedMessage:
    """Decode a single framed message from raw bytes.

    The data must include the 4-byte length prefix.

    Raises:
        ValueError: If the data is too short or malformed.
    """
    if len(data) < LENGTH_PREFIX_SIZE + HEADER_SIZE - LENGTH_PREFIX_SIZE:
        raise ValueError(f'Frame too short: {len(data)} bytes')

    total_len = struct.unpack('>I', data[:4])[0]
    msg_id, json_len = struct.unpack('>QI', data[4:16])

    if len(data) < 16 + json_len:
        raise ValueError(f'Frame truncated: expected {16 + json_len} bytes, got {len(data)}')

    json_bytes = data[16 : 16 + json_len]
    metadata = json.loads(json_bytes.decode('utf-8'))

    payload = data[16 + json_len : 4 + total_len]

    # Decompress gzip payload if indicated
    content_encoding = metadata.get('Content-Encoding', '')
    if content_encoding == 'gzip' and payload:
        payload = zlib.decompress(payload, zlib.MAX_WBITS | 16)

    return FramedMessage(message_id=msg_id, metadata=metadata, payload=payload)


class FrameBuffer:
    """Accumulates incoming bytes and yields complete frames.

    Handles partial reads - the data channel may deliver fragments.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[FramedMessage]:
        """Feed incoming data and return any complete frames."""
        self._buffer.extend(data)
        frames = []

        while len(self._buffer) >= LENGTH_PREFIX_SIZE:
            total_len = struct.unpack('>I', self._buffer[:4])[0]
            frame_size = LENGTH_PREFIX_SIZE + total_len

            if len(self._buffer) < frame_size:
                break  # Incomplete frame, wait for more data

            frame_data = bytes(self._buffer[:frame_size])
            self._buffer = self._buffer[frame_size:]
            frames.append(decode_frame(frame_data))

        return frames
