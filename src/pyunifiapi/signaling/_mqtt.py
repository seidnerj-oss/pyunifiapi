"""MQTT-based signaling for cloud WebRTC connections.

Uses AWS IoT MQTT over WebSocket (SigV4-signed) for SDP/ICE exchange
when establishing WebRTC data channels to cloud-connected controllers.

Replaces the legacy WebSocket-based signaling at device-airos.svc.ubnt.com.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import struct
import uuid as uuid_mod
from typing import Any
from urllib.parse import quote

import websockets

from pyunifiapi._constants import CLOUD_IOT_HOST, CLOUD_IOT_REGION, MQTT_ICE_COLLECT_TIMEOUT, MQTT_MESSAGE_TIMEOUT
from pyunifiapi._exceptions import SignalingError
from pyunifiapi._types import TurnCredentials

logger = logging.getLogger(__name__)

# MQTT packet types
MQTT_CONNECT = 1
MQTT_CONNACK = 2
MQTT_PUBLISH = 3
MQTT_PUBACK = 4
MQTT_SUBSCRIBE = 8
MQTT_SUBACK = 9
MQTT_PINGREQ = 12
MQTT_PINGRESP = 13
MQTT_DISCONNECT = 14


# --- Minimal MQTT framing ---


def _encode_remaining_length(length: int) -> bytes:
    """Encode MQTT remaining length (variable-length encoding)."""
    result = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        result.append(byte)
        if length == 0:
            break
    return bytes(result)


def _decode_remaining_length(data: bytes, offset: int) -> tuple[int, int]:
    """Decode MQTT remaining length. Returns (value, bytes_consumed)."""
    multiplier = 1
    value = 0
    idx = offset
    while True:
        byte = data[idx]
        value += (byte & 0x7F) * multiplier
        multiplier *= 128
        idx += 1
        if not (byte & 0x80):
            break
    return value, idx - offset


def _encode_utf8_string(s: str) -> bytes:
    """Encode a string with MQTT 2-byte length prefix."""
    encoded = s.encode('utf-8')
    return struct.pack('!H', len(encoded)) + encoded


def _build_connect_packet(client_id: str) -> bytes:
    """Build an MQTT CONNECT packet (v3.1.1, clean session)."""
    # Variable header
    var_header = bytearray()
    var_header += _encode_utf8_string('MQTT')  # Protocol Name
    var_header.append(4)  # Protocol Level (3.1.1)
    var_header.append(0x02)  # Connect Flags: Clean Session
    var_header += struct.pack('!H', 10)  # Keep Alive (10s, matches browser)

    # Payload
    payload = _encode_utf8_string(client_id)

    body = bytes(var_header) + payload
    return bytes([MQTT_CONNECT << 4]) + _encode_remaining_length(len(body)) + body


def _build_subscribe_packet(packet_id: int, topic: str, qos: int = 1) -> bytes:
    """Build an MQTT SUBSCRIBE packet."""
    var_header = struct.pack('!H', packet_id)
    payload = _encode_utf8_string(topic) + bytes([qos])
    body = var_header + payload
    return bytes([(MQTT_SUBSCRIBE << 4) | 0x02]) + _encode_remaining_length(len(body)) + body


def _build_publish_packet(topic: str, payload: bytes, qos: int = 1, packet_id: int = 0) -> bytes:
    """Build an MQTT PUBLISH packet."""
    var_header = _encode_utf8_string(topic)
    if qos > 0:
        var_header += struct.pack('!H', packet_id)
    flags = (MQTT_PUBLISH << 4) | (qos << 1)
    body = var_header + payload
    return bytes([flags]) + _encode_remaining_length(len(body)) + body


def _build_puback_packet(packet_id: int) -> bytes:
    """Build an MQTT PUBACK packet."""
    return bytes([MQTT_PUBACK << 4, 2]) + struct.pack('!H', packet_id)


def _build_pingreq_packet() -> bytes:
    """Build an MQTT PINGREQ packet."""
    return bytes([MQTT_PINGREQ << 4, 0])


def _build_disconnect_packet() -> bytes:
    """Build an MQTT DISCONNECT packet."""
    return bytes([MQTT_DISCONNECT << 4, 0])


def _parse_packet(data: bytes) -> tuple[int, int, bytes, int]:
    """Parse an MQTT packet. Returns (packet_type, flags, payload, total_length)."""
    byte0 = data[0]
    packet_type = byte0 >> 4
    flags = byte0 & 0x0F
    remaining_length, len_bytes = _decode_remaining_length(data, 1)
    header_len = 1 + len_bytes
    payload = data[header_len : header_len + remaining_length]
    return packet_type, flags, payload, header_len + remaining_length


def _parse_publish_packet(flags: int, payload: bytes) -> tuple[str, bytes, int | None]:
    """Parse a PUBLISH packet payload. Returns (topic, message, packet_id)."""
    topic_len = struct.unpack('!H', payload[:2])[0]
    topic = payload[2 : 2 + topic_len].decode('utf-8')
    offset = 2 + topic_len
    qos = (flags >> 1) & 0x03
    packet_id = None
    if qos > 0:
        packet_id = struct.unpack('!H', payload[offset : offset + 2])[0]
        offset += 2
    message = payload[offset:]
    return topic, message, packet_id


def _topic_matches(pattern: str, topic: str) -> bool:
    """Check if an MQTT topic matches a subscription pattern.

    Supports ``+`` (single-level) and ``#`` (multi-level) wildcards.
    """
    if pattern == topic:
        return True
    pat_parts = pattern.split('/')
    top_parts = topic.split('/')
    for i, pat in enumerate(pat_parts):
        if pat == '#':
            return True  # matches everything from here
        if i >= len(top_parts):
            return False
        if pat != '+' and pat != top_parts[i]:
            return False
    return len(pat_parts) == len(top_parts)


# --- SigV4 presigned WebSocket URL ---


def _build_mqtt_wss_url(
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str = CLOUD_IOT_REGION,
    host: str = CLOUD_IOT_HOST,
) -> str:
    """Build a SigV4 presigned WebSocket URL for AWS IoT MQTT."""
    now = datetime.datetime.now(datetime.UTC)
    datestamp = now.strftime('%Y%m%d')
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    service = 'iotdevicegateway'

    credential_scope = f'{datestamp}/{region}/{service}/aws4_request'
    credential = f'{access_key}/{credential_scope}'

    # Canonical query string (sorted)
    query_params = {
        'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
        'X-Amz-Credential': credential,
        'X-Amz-Date': amz_date,
        'X-Amz-SignedHeaders': 'host',
    }
    canonical_querystring = '&'.join(f'{quote(k, safe="")}={quote(v, safe="")}' for k, v in sorted(query_params.items()))

    # Canonical request
    canonical_request = '\n'.join(
        [
            'GET',
            '/mqtt',
            canonical_querystring,
            f'host:{host}\n',
            'host',
            hashlib.sha256(b'').hexdigest(),
        ]
    )

    # String to sign
    string_to_sign = '\n'.join(
        [
            'AWS4-HMAC-SHA256',
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest(),
        ]
    )

    # Signing key
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    signing_key = _sign(_sign(_sign(_sign(f'AWS4{secret_key}'.encode(), datestamp), region), service), 'aws4_request')

    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # Final URL
    signed_qs = f'{canonical_querystring}&X-Amz-Signature={signature}'
    if session_token:
        signed_qs += f'&X-Amz-Security-Token={quote(session_token, safe="")}'

    return f'wss://{host}/mqtt?{signed_qs}'


# --- MQTT Signaling Client ---


class MqttSignaling:
    """MQTT-based signaling for cloud WebRTC connections.

    Connects to AWS IoT MQTT via SigV4-signed WebSocket, and exchanges
    SDP offers/answers and ICE candidates for WebRTC peer connections.

    Usage::

        signaling = MqttSignaling(aws_credentials, identity_id)
        await signaling.connect()

        answer = await signaling.exchange_sdp(
            host_id='...',
            local_description=pc.localDescription.sdp,
            turn=turn_credentials,
        )
        # answer contains {'event': 'answer', 'answer': '<sdp>'}

        await signaling.close()
    """

    def __init__(self, aws_credentials: dict, identity_id: str) -> None:
        """
        Args:
            aws_credentials: Dict with access_key, secret_key, session_token, region.
            identity_id: The cognito identity ID from create-credentials response.
        """
        self._aws = aws_credentials
        self._identity_id = identity_id
        self._ws: Any = None
        self._packet_id_counter = 0
        self._pending_subscribes: dict[int, asyncio.Future[int]] = {}
        self._topic_handlers: dict[str, asyncio.Queue[dict]] = {}
        self._listener_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to AWS IoT MQTT broker via SigV4-signed WebSocket."""
        url = _build_mqtt_wss_url(
            access_key=self._aws['access_key'],
            secret_key=self._aws['secret_key'],
            session_token=self._aws['session_token'],
            region=self._aws.get('region', CLOUD_IOT_REGION),
        )

        self._ws = await websockets.connect(
            url,
            subprotocols=[websockets.Subprotocol('mqtt')],
            max_size=2**20,
        )

        # Send MQTT CONNECT
        client_id = f'mqtt-{uuid_mod.uuid4().hex[:12]}'
        await self._ws.send(_build_connect_packet(client_id))

        # Wait for CONNACK
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        ptype, _, payload, _ = _parse_packet(raw)
        if ptype != MQTT_CONNACK:
            raise SignalingError(f'Expected CONNACK, got packet type {ptype}')
        return_code = payload[1] if len(payload) >= 2 else 255
        if return_code != 0:
            raise SignalingError(f'MQTT CONNACK rejected with code {return_code}')

        self._connected = True
        self._listener_task = asyncio.create_task(self._listener_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info('Connected to MQTT broker at %s', CLOUD_IOT_HOST)

    def _next_packet_id(self) -> int:
        self._packet_id_counter += 1
        return self._packet_id_counter

    async def _subscribe(self, topic: str, qos: int = 1) -> None:
        """Subscribe to an MQTT topic."""
        assert self._ws is not None
        pid = self._next_packet_id()
        future: asyncio.Future[int] = asyncio.get_event_loop().create_future()
        self._pending_subscribes[pid] = future
        self._topic_handlers[topic] = asyncio.Queue()

        await self._ws.send(_build_subscribe_packet(pid, topic, qos))
        await asyncio.wait_for(future, timeout=10.0)
        logger.debug('Subscribed to %s', topic)

    async def _publish(self, topic: str, payload: dict, qos: int = 1) -> None:
        """Publish a JSON message to an MQTT topic."""
        assert self._ws is not None
        pid = self._next_packet_id() if qos > 0 else 0
        data = json.dumps(payload).encode('utf-8')
        await self._ws.send(_build_publish_packet(topic, data, qos, pid))
        logger.debug('Published to %s: %s', topic, payload.get('event', '?'))

    async def _listener_loop(self) -> None:
        """Listen for incoming MQTT packets and dispatch them."""
        assert self._ws is not None
        buf = bytearray()
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    raw = raw.encode('utf-8')
                buf.extend(raw)

                while len(buf) >= 2:
                    try:
                        ptype, flags, payload, total_len = _parse_packet(bytes(buf))
                    except (IndexError, struct.error):
                        break  # incomplete packet

                    if total_len > len(buf):
                        break  # incomplete packet

                    buf = buf[total_len:]
                    await self._handle_packet(ptype, flags, payload)

        except websockets.ConnectionClosed:
            logger.info('MQTT WebSocket closed')
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception('Error in MQTT listener')

    async def _handle_packet(self, ptype: int, flags: int, payload: bytes) -> None:
        """Handle a received MQTT packet."""
        if ptype == MQTT_PUBLISH:
            topic, message, packet_id = _parse_publish_packet(flags, payload)
            if packet_id is not None and self._ws:
                await self._ws.send(_build_puback_packet(packet_id))

            # Dispatch to topic handler (supports MQTT + wildcard matching)
            for sub_topic, queue in self._topic_handlers.items():
                if _topic_matches(sub_topic, topic):
                    try:
                        msg = json.loads(message.decode('utf-8'))
                        await queue.put(msg)
                    except json.JSONDecodeError:
                        logger.warning('Non-JSON message on %s: %s', topic, message[:100])

        elif ptype == MQTT_SUBACK:
            if len(payload) >= 3:
                pid = struct.unpack('!H', payload[:2])[0]
                future = self._pending_subscribes.pop(pid, None)
                if future and not future.done():
                    future.set_result(payload[2])

        elif ptype == MQTT_PINGRESP:
            pass  # Expected

        elif ptype == MQTT_PUBACK:
            pass  # QoS 1 ack

    async def _ping_loop(self) -> None:
        """Send periodic MQTT PINGREQ to keep the connection alive."""
        assert self._ws is not None
        try:
            while True:
                await asyncio.sleep(5)
                await self._ws.send(_build_pingreq_packet())
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    async def exchange_sdp(
        self,
        host_id: str,
        offer_sdp: str,
        local_candidates: list[str],
        turn: TurnCredentials,
        ice_servers: list[dict] | None = None,
    ) -> dict:
        """Exchange SDP offer/answer with a cloud-connected controller (cloud signaling).

        Publishes the pre-computed SDP offer and ICE candidates, then waits
        for the remote answer and remote ICE candidates via MQTT.

        Args:
            host_id: The controller's cloud device ID.
            offer_sdp: The local SDP offer string.
            local_candidates: List of local ICE candidate strings.
            turn: TURN credentials for ICE.
            ice_servers: Optional ICE server config for the offer message.

        Returns:
            Dict with the controller's SDP answer and ice_candidates.
        """
        connection_id = uuid_mod.uuid4().hex[:16]
        base_path = f'client/{self._identity_id}'
        pub_topic = f'{base_path}/device/{host_id}/connect/{connection_id}'
        sub_topic = f'{base_path}/{host_id}/connect/{connection_id}'

        await self._subscribe(sub_topic)

        stun_uri = turn.stun_urls[0] if turn.stun_urls else 'stun:stun.cloudflare.com:3478'
        ice_server_cfg = ice_servers or [
            {
                'urls': [stun_uri] + turn.turn_urls,
                'username': turn.turn_username,
                'credential': turn.turn_password,
            }
        ]

        seq = 0
        await self._publish(
            pub_topic,
            {
                'event': 'offer',
                'seq': seq,
                'offer': offer_sdp,
                'iceServers': ice_server_cfg,
            },
        )
        seq += 1
        logger.debug('Published offer (seq=0)')

        for candidate_str in local_candidates:
            await self._publish(
                pub_topic,
                {
                    'event': 'icecandidate',
                    'seq': seq,
                    'candidate': candidate_str,
                },
            )
            seq += 1
        logger.debug('Published %d local ICE candidates', len(local_candidates))

        queue = self._topic_handlers[sub_topic]
        answer: dict | None = None
        remote_candidates: list[dict] = []

        try:
            while True:
                msg = await asyncio.wait_for(queue.get(), timeout=MQTT_MESSAGE_TIMEOUT)
                event = msg.get('event', '')

                if event == 'answer':
                    answer = msg
                    logger.debug('Received SDP answer')
                    try:
                        while True:
                            msg = await asyncio.wait_for(queue.get(), timeout=MQTT_ICE_COLLECT_TIMEOUT)
                            event = msg.get('event', '')
                            if event == 'icecandidate':
                                remote_candidates.append(msg)
                                logger.debug('Received remote ICE candidate (seq=%s)', msg.get('seq'))
                            elif event == 'sdpcomplete':
                                break
                    except TimeoutError:
                        pass
                    break

                elif event == 'icecandidate':
                    remote_candidates.append(msg)

                elif event == 'sdpcomplete':
                    break

        except TimeoutError as e:
            if answer is None:
                raise SignalingError(f'Timed out waiting for SDP answer from {host_id}') from e

        if answer is None:
            raise SignalingError(f'No SDP answer received from {host_id}')

        answer['ice_candidates'] = remote_candidates
        return answer

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def close(self) -> None:
        """Close the MQTT connection."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
        if self._ws:
            try:
                await self._ws.send(_build_disconnect_packet())
            except Exception:
                pass
            await self._ws.close()
            self._ws = None
        self._connected = False
        self._topic_handlers.clear()
        self._pending_subscribes.clear()
