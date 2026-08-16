"""
纯 Python TFRecord / tf.Example 写入（无 TensorFlow / protobuf 依赖）。

CRC 使用 Castagnoli CRC32C；masked CRC 与 TF 一致：
  ((crc >> 15) | (crc << 17)) + 0xa282ead8
"""

from __future__ import annotations

import struct
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Union

FeatureValue = Union[Sequence[float], Sequence[int], Sequence[bytes], bytes, str, float, int]


# --- CRC32C (Castagnoli) ---
_CRC32C_TABLE: List[int] | None = None


def _crc32c_table() -> List[int]:
    global _CRC32C_TABLE
    if _CRC32C_TABLE is not None:
        return _CRC32C_TABLE
    poly = 0x82F63B78
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
        table.append(crc)
    _CRC32C_TABLE = table
    return table


def crc32c(data: bytes, crc: int = 0) -> int:
    table = _crc32c_table()
    crc = crc ^ 0xFFFFFFFF
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def masked_crc32c(data: bytes) -> int:
    c = crc32c(data)
    return (((c >> 15) | (c << 17)) + 0xA282EAD8) & 0xFFFFFFFF


# --- minimal protobuf wire encode ---


def _encode_varint(value: int) -> bytes:
    value &= (1 << 64) - 1
    out = bytearray()
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            out.append(bits | 0x80)
        else:
            out.append(bits)
            break
    return bytes(out)


def _encode_key(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_bytes_field(field_number: int, value: bytes) -> bytes:
    return _encode_key(field_number, 2) + _encode_varint(len(value)) + value


def _encode_float_field(field_number: int, value: float) -> bytes:
    return _encode_key(field_number, 5) + struct.pack("<f", float(value))


def _encode_int64_field(field_number: int, value: int) -> bytes:
    return _encode_key(field_number, 0) + _encode_varint(int(value))


def _encode_bytes_list(values: Sequence[bytes]) -> bytes:
    # BytesList { repeated bytes value = 1; }
    body = b"".join(_encode_bytes_field(1, v) for v in values)
    return body


def _encode_float_list(values: Sequence[float]) -> bytes:
    # FloatList { repeated float value = 1 [packed=true]; }
    packed = b"".join(struct.pack("<f", float(v)) for v in values)
    return _encode_bytes_field(1, packed)


def _encode_int64_list(values: Sequence[int]) -> bytes:
    # Int64List { repeated int64 value = 1 [packed=true]; }
    packed = b"".join(_encode_varint(int(v)) for v in values)
    return _encode_bytes_field(1, packed)


def _encode_feature(kind: str, values: Sequence[Any]) -> bytes:
    """
    Feature {
      oneof kind {
        BytesList bytes_list = 1;
        FloatList float_list = 2;
        Int64List int64_list = 3;
      }
    }
    """
    if kind == "bytes":
        inner = _encode_bytes_list([v if isinstance(v, (bytes, bytearray)) else str(v).encode("utf-8") for v in values])
        return _encode_bytes_field(1, inner)
    if kind == "float":
        inner = _encode_float_list([float(v) for v in values])
        return _encode_bytes_field(2, inner)
    if kind == "int64":
        inner = _encode_int64_list([int(v) for v in values])
        return _encode_bytes_field(3, inner)
    raise ValueError(f"unknown feature kind: {kind}")


def _encode_features(feature_map: Mapping[str, bytes]) -> bytes:
    """
    Features {
      map<string, Feature> feature = 1;
    }
    map entry: message { string key=1; Feature value=2; }
    """
    parts = []
    for key, feature_bytes in feature_map.items():
        entry = _encode_bytes_field(1, key.encode("utf-8")) + _encode_bytes_field(2, feature_bytes)
        parts.append(_encode_bytes_field(1, entry))
    return b"".join(parts)


def encode_example(features: Mapping[str, Dict[str, Any]]) -> bytes:
    """
    features: { name: {"bytes_list": [...] } | {"float_list": [...]} | {"int64_list": [...]} }
    """
    encoded: Dict[str, bytes] = {}
    for name, spec in features.items():
        if "bytes_list" in spec:
            vals = spec["bytes_list"]
            if isinstance(vals, (bytes, bytearray, str)):
                vals = [vals]
            encoded[name] = _encode_feature("bytes", list(vals))
        elif "float_list" in spec:
            vals = spec["float_list"]
            if isinstance(vals, (int, float)):
                vals = [vals]
            encoded[name] = _encode_feature("float", list(vals))
        elif "int64_list" in spec:
            vals = spec["int64_list"]
            if isinstance(vals, int):
                vals = [vals]
            encoded[name] = _encode_feature("int64", list(vals))
        else:
            raise ValueError(f"feature {name} missing list type")
    features_msg = _encode_features(encoded)
    # Example { Features features = 1; }
    return _encode_bytes_field(1, features_msg)


def write_tfrecord_bytes(examples: Iterable[bytes]) -> bytes:
    buf = bytearray()
    for raw in examples:
        length = len(raw)
        buf.extend(struct.pack("<Q", length))
        buf.extend(struct.pack("<I", masked_crc32c(struct.pack("<Q", length))))
        buf.extend(raw)
        buf.extend(struct.pack("<I", masked_crc32c(raw)))
    return bytes(buf)


def example_from_step(step: Mapping[str, Any], *, episode_id: str = "", step_index: int = 0) -> bytes:
    obs = step.get("observation") if isinstance(step.get("observation"), dict) else {}
    action = step.get("action") if isinstance(step.get("action"), dict) else {}
    features = {
        "episode_id": {"bytes_list": [str(episode_id).encode("utf-8")]},
        "step_index": {"int64_list": [int(step_index)]},
        "observation/state": {"float_list": list(obs.get("state") or [])},
        "observation/torque": {"float_list": list(obs.get("torque") or [])},
        "observation/force": {"float_list": list(obs.get("force") or [0, 0, 0, 0, 0, 0])},
        "observation/tactile": {"float_list": list(obs.get("tactile") or [])},
        "action/label": {"bytes_list": [str(action.get("label") or "idle").encode("utf-8")]},
        "action/label_text": {"bytes_list": [str(action.get("label_text") or "").encode("utf-8")]},
        "reward": {"float_list": [float(step.get("reward") or 0)]},
        "discount": {"float_list": [float(step.get("discount") if step.get("discount") is not None else 1.0)]},
        "is_first": {"int64_list": [1 if step.get("is_first") else 0]},
        "is_last": {"int64_list": [1 if step.get("is_last") else 0]},
        "language_instruction": {
            "bytes_list": [str(step.get("language_instruction") or "").encode("utf-8")]
        },
        "timestamp": {"float_list": [float(step.get("timestamp") or 0)]},
    }
    return encode_example(features)
