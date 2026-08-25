"""Strict pure encoders for statically recovered phone-integration requests.

Nothing in this module can connect, subscribe, enqueue, retry, or write.  Encoded
frames are deliberately available only through a test-named accessor, and all
requests remain ineligible for hardware use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from string import hexdigits
from typing import Iterable
import unicodedata

from .uuids import VENDOR_CHARACTERISTIC_33F3


class OfflinePhoneOperation(str, Enum):
    DOWNLOAD_COMPLETED = "download_completed"
    OPEN_WIFI_AP_MODE = "open_wifi_ap_mode"
    APP_ID = "app_id"
    CHAT_CONTENT = "chat_content"
    CONTACT_CRC = "contact_crc"
    CONTACT_INFO = "contact_info"
    E_CARD_CONTENT = "e_card_content"
    E_CARD_CRC = "e_card_crc"
    NOTIFICATION = "notification"
    PHONE_MAC = "phone_mac"
    SMS_REPLY_CONTENT = "sms_reply_content"
    SMS_REPLY_CRC = "sms_reply_crc"
    SMS_REPLY_ACK = "sms_reply_ack"
    USER_INFO = "user_info"
    WIFI_HOTSPOT_INFO = "wifi_hotspot_info"
    WIFI_HOTSPOT_INFO_EX = "wifi_hotspot_info_ex"
    WORSHIP_INFO = "worship_info"


@dataclass(frozen=True)
class OfflinePhoneSafety:
    transport_integration: bool = False
    apk_queue_clearing_reproduced: bool = False
    apk_write_retry_reproduced: bool = False
    apk_local_side_effects_reproduced: bool = False


_OFFLINE_SAFETY = OfflinePhoneSafety()


@dataclass(frozen=True, init=False, repr=False)
class OfflinePhoneRequest:
    operation: OfflinePhoneOperation
    privacy_class: str
    source_enqueue_position: str
    known_omissions: tuple[str, ...]
    _frames: tuple[bytes, ...] = field(repr=False)

    def __init__(self) -> None:
        raise TypeError("offline phone requests use closed encoder functions")

    @classmethod
    def _create(
        cls,
        operation: OfflinePhoneOperation,
        privacy_class: str,
        frames: Iterable[bytes],
        *,
        source_enqueue_position: str = "tail",
        known_omissions: tuple[str, ...] = (),
    ) -> "OfflinePhoneRequest":
        if type(operation) is not OfflinePhoneOperation:
            raise TypeError("operation must be an OfflinePhoneOperation")
        encoded = tuple(bytes(frame) for frame in frames)
        if not encoded or any(len(frame) != 20 for frame in encoded):
            raise ValueError("an offline phone request needs one or more 20-byte frames")
        if source_enqueue_position not in {"front", "tail"}:
            raise ValueError("unknown recovered enqueue position")
        request = object.__new__(cls)
        object.__setattr__(request, "operation", operation)
        object.__setattr__(request, "privacy_class", privacy_class)
        object.__setattr__(request, "source_enqueue_position", source_enqueue_position)
        object.__setattr__(request, "known_omissions", tuple(known_omissions))
        object.__setattr__(request, "_frames", encoded)
        return request

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def safety(self) -> OfflinePhoneSafety:
        return _OFFLINE_SAFETY

    @property
    def parity_scope(self) -> str:
        return "wire_frames_only"

    @property
    def risk_class(self) -> str:
        if self.operation in {
            OfflinePhoneOperation.OPEN_WIFI_AP_MODE,
            OfflinePhoneOperation.WIFI_HOTSPOT_INFO,
            OfflinePhoneOperation.WIFI_HOTSPOT_INFO_EX,
        }:
            return "network_mutation"
        if self.operation is OfflinePhoneOperation.USER_INFO:
            return "personal_profile_mutation"
        if self.operation in {
            OfflinePhoneOperation.CONTACT_CRC,
            OfflinePhoneOperation.E_CARD_CRC,
            OfflinePhoneOperation.SMS_REPLY_CRC,
        }:
            return "private_sync_fingerprint"
        return "private_or_device_mutation"

    @property
    def integrity_role(self) -> str | None:
        if self.risk_class == "private_sync_fingerprint":
            return "opaque_sync_fingerprint_not_security"
        return None

    def synthetic_frames_for_test(self) -> tuple[bytes, ...]:
        return tuple(bytes(frame) for frame in self._frames)

    def __repr__(self) -> str:
        return (
            "OfflinePhoneRequest("
            f"operation={self.operation.value!r}, privacy_class={self.privacy_class!r}, "
            "frame=<redacted>, "
            "hardware_eligible=False, hardware_verified=False)"
        )


@dataclass(frozen=True, init=False, repr=False)
class UnsupportedPhoneOperation:
    operation: OfflinePhoneOperation
    reason_code: str

    def __init__(self) -> None:
        raise TypeError("unsupported operation descriptions use closed constructors")

    @classmethod
    def _create(
        cls, operation: OfflinePhoneOperation, reason_code: str
    ) -> "UnsupportedPhoneOperation":
        result = object.__new__(cls)
        object.__setattr__(result, "operation", operation)
        object.__setattr__(result, "reason_code", reason_code)
        return result

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "UnsupportedPhoneOperation("
            f"operation={self.operation.value!r}, reason_code={self.reason_code!r}, "
            "hardware_eligible=False)"
        )


def _integer(value: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    return value


def _u8(value: int, label: str) -> int:
    result = _integer(value, label)
    if not 0 <= result <= 0xFF:
        raise ValueError(f"{label} must fit one unsigned byte")
    return result


def _bool(value: bool, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a boolean")
    return value


def _utf8(
    value: str,
    label: str,
    *,
    maximum: int,
    allow_empty: bool = True,
) -> bytes:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if unicodedata.normalize("NFC", value) != value or not value.isprintable():
        raise ValueError(f"{label} must be normalized printable text")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError(f"{label} cannot contain control or format characters")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be valid Unicode text") from exc
    if not allow_empty and not encoded:
        raise ValueError(f"{label} cannot be empty")
    if len(encoded) > maximum:
        raise ValueError(f"UTF-8 {label} must fit {maximum} bytes without truncation")
    return encoded


def _records(values, record_type, label: str, *, maximum: int | None = None):
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{label} must be an iterable of records")
    result = tuple(values)
    if not result:
        raise ValueError(f"{label} cannot be empty")
    if maximum is not None and len(result) > maximum:
        raise ValueError(f"{label} supports at most {maximum} records")
    if any(type(value) is not record_type for value in result):
        raise TypeError(f"{label} contains an invalid record type")
    return result


def _frame(*prefix: int, payload: bytes = b"") -> bytes:
    encoded = bytes(prefix) + payload
    if len(encoded) > 20:
        raise ValueError("frame data exceeds twenty bytes")
    return encoded + bytes(20 - len(encoded))


def _single(
    operation: OfflinePhoneOperation,
    privacy_class: str,
    *prefix: int,
    source_enqueue_position: str = "tail",
) -> OfflinePhoneRequest:
    return OfflinePhoneRequest._create(
        operation,
        privacy_class,
        (_frame(*prefix),),
        source_enqueue_position=source_enqueue_position,
    )


@dataclass(frozen=True, repr=False)
class ContactRecord:
    contact_id: int
    phone_number: str
    name: str

    def __post_init__(self) -> None:
        _u8(self.contact_id, "contact id")
        if self.contact_id > 15:
            raise ValueError("contact id must be between 0 and 15")
        _utf8(self.phone_number, "phone number", maximum=18)
        _utf8(self.name, "contact name", maximum=54)

    def __repr__(self) -> str:
        return f"ContactRecord(contact_id={self.contact_id}, private_fields=<redacted>)"


@dataclass(frozen=True, repr=False)
class ECardRecord:
    card_id: int
    name: str
    content: str

    def __post_init__(self) -> None:
        _u8(self.card_id, "e-card id")
        if self.card_id > 15:
            raise ValueError("e-card id must be between 0 and 15")
        _utf8(self.name, "e-card name", maximum=59)
        _utf8(self.content, "e-card content", maximum=330)

    def __repr__(self) -> str:
        return f"ECardRecord(card_id={self.card_id}, private_fields=<redacted>)"


@dataclass(frozen=True, repr=False)
class SmsReplyRecord:
    reply_id: int
    content: str

    def __post_init__(self) -> None:
        _u8(self.reply_id, "SMS reply id")
        if self.reply_id > 15:
            raise ValueError("SMS reply id must be between 0 and 15")
        _utf8(self.content, "SMS reply content", maximum=120)

    def __repr__(self) -> str:
        return f"SmsReplyRecord(reply_id={self.reply_id}, content=<redacted>)"


def encode_download_completed() -> OfflinePhoneRequest:
    return _single(
        OfflinePhoneOperation.DOWNLOAD_COMPLETED, "device_transfer_state", 0x54, 0x07
    )


def encode_open_wifi_ap_mode(*, enabled: bool) -> OfflinePhoneRequest:
    if not _bool(enabled, "enabled"):
        raise ValueError("the recovered wire command only represents opening Wi-Fi AP mode")
    return _single(
        OfflinePhoneOperation.OPEN_WIFI_AP_MODE,
        "network_control",
        0x54,
        0x13,
        1,
        source_enqueue_position="front",
    )


def _fixed_text(
    operation: OfflinePhoneOperation, opcode: int, value: str, label: str, privacy: str
) -> OfflinePhoneRequest:
    encoded = _utf8(value, label, maximum=18, allow_empty=False)
    return OfflinePhoneRequest._create(
        operation, privacy, (_frame(opcode, payload=encoded),)
    )


def encode_app_id(value: str) -> OfflinePhoneRequest:
    return _fixed_text(
        OfflinePhoneOperation.APP_ID, 0x48, value, "app id", "private_identifier"
    )


def encode_phone_mac(value: str) -> OfflinePhoneRequest:
    return _fixed_text(
        OfflinePhoneOperation.PHONE_MAC,
        0x49,
        value,
        "phone MAC",
        "private_device_identifier",
    )


def encode_chat_content(*, content_type: int, content: str) -> OfflinePhoneRequest:
    kind = _u8(content_type, "chat content type")
    limit = 1600 if kind == 1 else 384
    encoded = _utf8(content, "chat content", maximum=limit, allow_empty=False)
    pieces = (len(encoded) // 17) + 1
    frames = [
        _frame(0x4F, kind, index + 1, payload=encoded[index * 17 : (index + 1) * 17])
        for index in range(pieces)
    ]
    frames.append(_frame(0x4F, kind, 0xFF))
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.CHAT_CONTENT, "private_conversation", frames
    )


def encode_contact_crc(crc_hex: str) -> OfflinePhoneRequest:
    if not isinstance(crc_hex, str):
        raise TypeError("contact CRC must be a hexadecimal string")
    if len(crc_hex) != 8 or any(char not in hexdigits for char in crc_hex):
        raise ValueError("contact sync fingerprint must contain exactly eight hex digits")
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.CONTACT_CRC,
        "private_contact_fingerprint",
        (_frame(0x46, payload=bytes.fromhex(crc_hex)),),
    )


def encode_contact_info(records: Iterable[ContactRecord]) -> OfflinePhoneRequest:
    items = _records(records, ContactRecord, "contacts", maximum=16)
    if len({item.contact_id for item in items}) != len(items):
        raise ValueError("contact ids must be unique")
    frames: list[bytes] = []
    for record_index, item in enumerate(items):
        identifier = item.contact_id << 4
        phone = _utf8(item.phone_number, "phone number", maximum=18)
        frames.append(_frame(0x47, identifier, payload=phone))
        name = _utf8(item.name, "contact name", maximum=54)
        piece_count = (len(name) // 18) + 1
        for piece_index in range(min(piece_count, 3)):
            terminal = piece_index == piece_count - 1 or piece_index == 2
            flags = 0
            if terminal:
                flags = 0x0C if record_index == len(items) - 1 else 0x04
            header = identifier | (piece_index + 1) | flags
            frames.append(
                _frame(
                    0x47,
                    header,
                    payload=name[piece_index * 18 : (piece_index + 1) * 18],
                )
            )
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.CONTACT_INFO, "private_contacts", frames
    )


def _fragment_fifteen(opcode: int, subcommand: int, identifier: int, data: bytes):
    count = (len(data) // 15) + 1
    return [
        _frame(
            opcode,
            subcommand,
            identifier,
            count,
            index + 1,
            payload=data[index * 15 : (index + 1) * 15],
        )
        for index in range(count)
    ]


def encode_e_card_content(records: Iterable[ECardRecord]) -> OfflinePhoneRequest:
    items = _records(records, ECardRecord, "e-cards", maximum=10)
    if len({item.card_id for item in items}) != len(items):
        raise ValueError("e-card ids must be unique")
    frames: list[bytes] = []
    for item in items:
        name = _utf8(item.name, "e-card name", maximum=59)
        content = _utf8(item.content, "e-card content", maximum=330)
        if name:
            frames.extend(_fragment_fifteen(0x4C, 4, item.card_id, name))
        if content:
            frames.extend(_fragment_fifteen(0x4C, 5, item.card_id, content))
    if not frames:
        raise ValueError("e-card content would produce no Bluetooth frames")
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.E_CARD_CONTENT, "private_e_card_content", frames
    )


def _crc_update(seed: int, text: str) -> int:
    if not text:
        return 0
    value = seed & 0xFFFFFFFF
    for byte in text.encode("utf-8"):
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
    return value & 0xFFFFFFFF


def _crc_frames(opcode: int, values: tuple[int, ...]) -> list[bytes]:
    total = sum(values) & 0xFFFFFFFF
    frames = [_frame(opcode, 1, len(values), payload=total.to_bytes(4, "little"))]
    for base in range(0, len(values), 4):
        payload = b"".join(value.to_bytes(4, "little") for value in values[base : base + 4])
        frames.append(_frame(opcode, 2, base + 1, 0, payload=payload))
    return frames


def encode_e_card_crc(records: Iterable[ECardRecord]) -> OfflinePhoneRequest:
    items = _records(records, ECardRecord, "e-cards", maximum=10)
    if len({item.card_id for item in items}) != len(items):
        raise ValueError("e-card ids must be unique")
    if any(not item.name or not item.content for item in items):
        raise ValueError("e-card fingerprints require non-empty name and content")
    values = tuple(
        _crc_update(_crc_update(0xFFFFFFFF, item.name), item.content) for item in items
    )
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.E_CARD_CRC,
        "private_e_card_fingerprints",
        _crc_frames(0x4C, values),
    )


def encode_sms_reply_content(records: Iterable[SmsReplyRecord]) -> OfflinePhoneRequest:
    items = _records(records, SmsReplyRecord, "SMS replies", maximum=5)
    if len({item.reply_id for item in items}) != len(items):
        raise ValueError("SMS reply ids must be unique")
    frames: list[bytes] = []
    for item in items:
        content = _utf8(
            item.content, "SMS reply content", maximum=120, allow_empty=False
        )
        frames.extend(_fragment_fifteen(0x4D, 4, item.reply_id, content))
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.SMS_REPLY_CONTENT, "private_message_templates", frames
    )


def encode_sms_reply_crc(records: Iterable[SmsReplyRecord]) -> OfflinePhoneRequest:
    items = _records(records, SmsReplyRecord, "SMS replies", maximum=5)
    if len({item.reply_id for item in items}) != len(items):
        raise ValueError("SMS reply ids must be unique")
    if any(not item.content for item in items):
        raise ValueError("SMS reply fingerprints require non-empty content")
    values = tuple(_crc_update(0xFFFFFFFF, item.content) for item in items)
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.SMS_REPLY_CRC,
        "private_message_template_fingerprints",
        _crc_frames(0x4D, values),
    )


def encode_sms_reply_ack(*, reply_id: int) -> OfflinePhoneRequest:
    return _single(
        OfflinePhoneOperation.SMS_REPLY_ACK,
        "private_message_action",
        0x4D,
        7,
        _u8(reply_id, "SMS reply id"),
    )


def encode_user_info(
    *, gender_bit_set: bool, age: int, height: int, weight: int, unit: int
) -> OfflinePhoneRequest:
    gender_flag = _bool(gender_bit_set, "gender bit")
    encoded_age = _u8(age, "age")
    if encoded_age > 127:
        raise ValueError("age must fit seven bits without colliding with the gender bit")
    return _single(
        OfflinePhoneOperation.USER_INFO,
        "sensitive_personal_profile",
        0x02,
        encoded_age | (0x80 if gender_flag else 0),
        _u8(height, "height"),
        _u8(weight, "weight"),
        _u8(unit, "unit"),
    )


def _wifi_frames(ssid: str, password: str) -> list[bytes]:
    encoded_ssid = _utf8(ssid, "Wi-Fi SSID", maximum=2175, allow_empty=False)
    encoded_password = _utf8(
        password, "Wi-Fi password", maximum=2175, allow_empty=False
    )
    frames: list[bytes] = []
    for subcommand, value, label in (
        (1, encoded_ssid, "Wi-Fi SSID"),
        (2, encoded_password, "Wi-Fi password"),
    ):
        if value and len(value) % 17 == 0:
            raise ValueError(
                f"{label} cannot be an exact 17-byte multiple because the recovered "
                "source drops the final piece"
            )
        count = (len(value) + 16) // 17
        for index in range(count):
            header = index | (0x80 if index == count - 1 else 0)
            frames.append(
                _frame(
                    0x54,
                    subcommand,
                    header,
                    payload=value[index * 17 : (index + 1) * 17],
                )
            )
    return frames


def encode_wifi_hotspot_info(*, ssid: str, password: str) -> OfflinePhoneRequest:
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.WIFI_HOTSPOT_INFO,
        "private_network_credentials",
        _wifi_frames(ssid, password),
    )


def encode_wifi_hotspot_info_ex(
    *, ssid: str, password: str, timeout_seconds: int
) -> OfflinePhoneRequest:
    timeout = _integer(timeout_seconds, "timeout seconds")
    if not 1 <= timeout <= 0x7FFFFFFF:
        raise ValueError("timeout seconds must be a positive signed 32-bit value")
    return OfflinePhoneRequest._create(
        OfflinePhoneOperation.WIFI_HOTSPOT_INFO_EX,
        "private_network_credentials",
        _wifi_frames(ssid, password),
        known_omissions=("timeout_callback_state", "timeout_timer"),
    )


def encode_worship_info(*, first: int, second: int) -> OfflinePhoneRequest:
    return _single(
        OfflinePhoneOperation.WORSHIP_INFO,
        "personal_practice_setting",
        0x78,
        7,
        _u8(first, "first neutral worship field"),
        _u8(second, "second neutral worship field"),
        source_enqueue_position="front",
    )


def describe_unsupported_notification() -> UnsupportedPhoneOperation:
    return UnsupportedPhoneOperation._create(
        OfflinePhoneOperation.NOTIFICATION,
        "stateful_sequence_and_deduplication",
    )
