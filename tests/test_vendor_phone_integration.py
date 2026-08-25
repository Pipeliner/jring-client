import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_phone_integration import (
    ContactRecord,
    ECardRecord,
    OfflinePhoneRequest,
    OfflinePhoneOperation,
    SmsReplyRecord,
    describe_unsupported_notification,
    encode_app_id,
    encode_chat_content,
    encode_contact_crc,
    encode_contact_info,
    encode_download_completed,
    encode_e_card_content,
    encode_e_card_crc,
    encode_open_wifi_ap_mode,
    encode_phone_mac,
    encode_sms_reply_ack,
    encode_sms_reply_content,
    encode_sms_reply_crc,
    encode_user_info,
    encode_wifi_hotspot_info,
    encode_wifi_hotspot_info_ex,
    encode_worship_info,
)


def _frames(request):
    return request.synthetic_frames_for_test()


def test_simple_main_channel_frames_are_exactly_twenty_bytes():
    completed = encode_download_completed()
    opened = encode_open_wifi_ap_mode(enabled=True)
    ack = encode_sms_reply_ack(reply_id=7)
    worship = encode_worship_info(first=2, second=9)

    assert _frames(completed) == (bytes((0x54, 0x07)) + bytes(18),)
    assert _frames(opened) == (bytes((0x54, 0x13, 1)) + bytes(17),)
    assert _frames(ack) == (bytes((0x4D, 0x07, 7)) + bytes(17),)
    assert _frames(worship) == (bytes((0x78, 0x07, 2, 9)) + bytes(16),)

    with pytest.raises(ValueError):
        encode_open_wifi_ap_mode(enabled=False)


def test_app_id_and_phone_mac_use_fixed_utf8_fields_without_truncation():
    app = encode_app_id("client-42")
    mac = encode_phone_mac("AA:BB:CC:DD:EE:FF")

    assert _frames(app) == (bytes((0x48,)) + b"client-42" + bytes(10),)
    assert _frames(mac) == (bytes((0x49,)) + b"AA:BB:CC:DD:EE:FF" + bytes(2),)


@pytest.mark.parametrize("encoder", [encode_app_id, encode_phone_mac])
@pytest.mark.parametrize(
    "value",
    ["x" * 19, "a" * 17 + "\N{LATIN SMALL LETTER E WITH ACUTE}", "a\x00b"],
)
def test_fixed_text_fields_reject_truncation_and_padding_ambiguity(encoder, value):
    with pytest.raises(ValueError):
        encoder(value)


def test_chat_content_uses_numbered_seventeen_byte_pieces_and_terminator():
    request = encode_chat_content(content_type=1, content="x" * 18)

    assert _frames(request) == (
        bytes((0x4F, 1, 1)) + b"x" * 17,
        bytes((0x4F, 1, 2)) + b"x" + bytes(16),
        bytes((0x4F, 1, 0xFF)) + bytes(17),
    )


def test_chat_exact_piece_boundary_preserves_the_observed_empty_piece():
    frames = _frames(encode_chat_content(content_type=2, content="x" * 17))

    assert frames[1] == bytes((0x4F, 2, 2)) + bytes(17)
    assert frames[2] == bytes((0x4F, 2, 0xFF)) + bytes(17)


@pytest.mark.parametrize(
    "content_type,content",
    [(1, "x" * 1601), (0, "x" * 385), (256, "ok"), (True, "ok"), (1, "")],
)
def test_chat_rejects_vendor_truncation_empty_content_and_wrapping(content_type, content):
    with pytest.raises((TypeError, ValueError)):
        encode_chat_content(content_type=content_type, content=content)


def test_contact_crc_requires_fixed_width_and_preserves_hex_byte_order():
    assert _frames(encode_contact_crc("12345678")) == (
        bytes((0x46, 0x12, 0x34, 0x56, 0x78)) + bytes(15),
    )
    for ambiguous in ("1", "0100", "010000"):
        with pytest.raises(ValueError):
            encode_contact_crc(ambiguous)


def test_contact_info_marks_piece_and_last_record_in_the_header():
    records = (
        ContactRecord(contact_id=2, phone_number="123", name="A" * 19),
        ContactRecord(contact_id=3, phone_number="456", name="B"),
    )
    frames = _frames(encode_contact_info(records))

    assert frames[0] == bytes((0x47, 0x20)) + b"123" + bytes(15)
    assert frames[1][0:2] == bytes((0x47, 0x21))
    assert frames[2][0:2] == bytes((0x47, 0x26))
    assert frames[3] == bytes((0x47, 0x30)) + b"456" + bytes(15)
    assert frames[4][0:2] == bytes((0x47, 0x3D))


def test_contact_fields_reject_modulo_ids_and_source_truncation():
    with pytest.raises(ValueError):
        ContactRecord(contact_id=16, phone_number="1", name="name")
    with pytest.raises(ValueError):
        ContactRecord(contact_id=1, phone_number="x" * 19, name="name")
    with pytest.raises(ValueError):
        ContactRecord(contact_id=1, phone_number="1", name="x" * 55)


def test_e_card_content_encodes_name_then_content_in_fifteen_byte_pieces():
    item = ECardRecord(card_id=4, name="N", content="C" * 16)
    frames = _frames(encode_e_card_content((item,)))

    assert frames[0] == bytes((0x4C, 4, 4, 1, 1)) + b"N" + bytes(14)
    assert frames[1] == bytes((0x4C, 5, 4, 2, 1)) + b"C" * 15
    assert frames[2] == bytes((0x4C, 5, 4, 2, 2)) + b"C" + bytes(14)


def test_e_card_and_sms_exact_boundaries_include_observed_empty_final_piece():
    e_card = _frames(
        encode_e_card_content((ECardRecord(card_id=0, name="", content="x" * 15),))
    )
    sms = _frames(
        encode_sms_reply_content((SmsReplyRecord(reply_id=0, content="x" * 15),))
    )

    assert e_card[-1] == bytes((0x4C, 5, 0, 2, 2)) + bytes(15)
    assert sms[-1] == bytes((0x4D, 4, 0, 2, 2)) + bytes(15)


def test_crc_sequences_have_total_then_little_endian_per_item_crc_frames():
    e_cards = (
        ECardRecord(card_id=0, name="alpha", content="one"),
        ECardRecord(card_id=1, name="beta", content="two"),
    )
    replies = (
        SmsReplyRecord(reply_id=0, content="yes"),
        SmsReplyRecord(reply_id=1, content="no"),
    )

    e_frames = _frames(encode_e_card_crc(e_cards))
    s_frames = _frames(encode_sms_reply_crc(replies))
    assert e_frames == (
        bytes.fromhex("4c0102a3bf1db600000000000000000000000000"),
        bytes.fromhex("4c020100ea585d6eb966c0470000000000000000"),
    )
    assert s_frames == (
        bytes.fromhex("4d010236a26e2200000000000000000000000000"),
        bytes.fromhex("4d02010056ca188ae0d755980000000000000000"),
    )


def test_user_profile_layout_is_explicit_and_does_not_hide_service_state():
    request = encode_user_info(
        gender_bit_set=True, age=40, height=175, weight=72, unit=1
    )

    assert _frames(request) == (bytes((0x02, 0xA8, 175, 72, 1)) + bytes(15),)


@pytest.mark.parametrize("age", [-1, 128, True])
def test_user_age_cannot_collide_with_the_gender_bit(age):
    with pytest.raises((TypeError, ValueError)):
        encode_user_info(
            gender_bit_set=False, age=age, height=170, weight=70, unit=0
        )


def test_wifi_credentials_are_separate_private_fragment_streams():
    frames = _frames(encode_wifi_hotspot_info(ssid="ring-net", password="secret"))

    assert frames == (
        bytes((0x54, 1, 0x80)) + b"ring-net" + bytes(9),
        bytes((0x54, 2, 0x80)) + b"secret" + bytes(11),
    )


def test_wifi_ex_has_identical_writes_but_validates_unreproduced_timeout_state():
    basic = _frames(encode_wifi_hotspot_info(ssid="net", password="pw"))
    extended = _frames(
        encode_wifi_hotspot_info_ex(ssid="net", password="pw", timeout_seconds=90)
    )

    assert extended == basic
    request = encode_wifi_hotspot_info_ex(
        ssid="net", password="pw", timeout_seconds=90
    )
    assert request.parity_scope == "wire_frames_only"
    assert request.known_omissions == ("timeout_callback_state", "timeout_timer")


@pytest.mark.parametrize(
    "ssid,password",
    [("x" * 17, "pw"), ("net", "x" * 34), ("", "pw"), ("net", "")],
)
def test_wifi_rejects_empty_ssid_and_source_exact_boundary_data_loss(ssid, password):
    with pytest.raises(ValueError):
        encode_wifi_hotspot_info(ssid=ssid, password=password)


def test_notification_is_typed_unsupported_without_retaining_private_content():
    result = describe_unsupported_notification()

    assert result.operation is OfflinePhoneOperation.NOTIFICATION
    assert result.reason_code == "stateful_sequence_and_deduplication"
    assert result.hardware_eligible is False
    assert not hasattr(result, "content")


def test_requests_are_closed_offline_private_and_repr_redacted():
    request = encode_wifi_hotspot_info(ssid="my-private-network", password="top-secret")
    rendered = repr(request)

    assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert request.maturity == "static_apk_only"
    assert request.hardware_eligible is False
    assert request.hardware_verified is False
    assert request.safety.transport_integration is False
    assert request.safety.apk_queue_clearing_reproduced is False
    assert request.safety.apk_write_retry_reproduced is False
    assert request.safety.apk_local_side_effects_reproduced is False
    assert "my-private-network" not in rendered
    assert "top-secret" not in rendered
    assert "frame=<redacted>" in rendered
    assert "frame_count" not in rendered


@pytest.mark.parametrize(
    "unsafe",
    [
        "line\nbreak",
        "escape\x1b",
        "right\u202eto-left",
        "zero\u200bwidth",
        "e\u0301",
        "\ud800",
    ],
)
def test_private_text_rejects_controls_formatting_and_malformed_unicode(unsafe):
    with pytest.raises(ValueError):
        encode_app_id(unsafe)


def test_sync_fingerprints_are_explicitly_non_security_and_ids_are_unique():
    request = encode_contact_crc("12345678")
    assert request.integrity_role == "opaque_sync_fingerprint_not_security"
    assert request.risk_class == "private_sync_fingerprint"

    duplicate_cards = (
        ECardRecord(card_id=1, name="a", content="b"),
        ECardRecord(card_id=1, name="c", content="d"),
    )
    with pytest.raises(ValueError):
        encode_e_card_crc(duplicate_cards)


def test_private_record_repr_and_request_construction_are_closed():
    contact = ContactRecord(contact_id=1, phone_number="private-phone", name="private-name")
    card = ECardRecord(card_id=1, name="private-card", content="private-content")
    reply = SmsReplyRecord(reply_id=1, content="private-reply")

    assert "private-phone" not in repr(contact)
    assert "private-name" not in repr(contact)
    assert "private-card" not in repr(card)
    assert "private-content" not in repr(card)
    assert "private-reply" not in repr(reply)
    with pytest.raises(TypeError):
        OfflinePhoneRequest()
