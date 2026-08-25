"""Local-only inventory of statically supported non-health capability evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NonHealthCapability:
    name: str
    label: str
    group: str
    description: str
    evidence: str
    maturity: str
    meaning: str
    input_candidate: bool
    hardware_verified: bool = False
    live_available: bool = False
    input_eligible: bool = False


_CAPABILITIES = (
    NonHealthCapability(
        "standard_hid_metadata",
        "Standard HID metadata",
        "standard_metadata",
        "selected-device service and characteristic inventory; report values are not read",
        "bluetooth_standard",
        "selected_device_metadata",
        "standard_hid",
        False,
    ),
    NonHealthCapability(
        "classic_profile_attachment",
        "Classic profile attachment",
        "classic_bluetooth",
        "Android bond/profile/socket attachment plumbing; separate from vendor GATT and not a HID capability",
        "static_apk",
        "offline_behavior_evidence",
        "platform_plumbing",
        False,
    ),
    NonHealthCapability(
        "classic_rfcomm_ota_transport",
        "Classic RFCOMM OTA transport",
        "classic_bluetooth",
        "embedded OTA helper exposes classic socket creation and close; no Python socket transport",
        "static_apk",
        "offline_behavior_evidence",
        "file_transfer_transport",
        False,
    ),
    NonHealthCapability(
        "classic_bt_info_callback",
        "Classic Bluetooth info callback",
        "classic_bluetooth",
        "offline callback decoder preserves two neutral non-identifier values",
        "static_apk",
        "offline_decoder",
        "classic_metadata",
        False,
    ),
    NonHealthCapability(
        "classic_bt_name_callback",
        "Classic Bluetooth name callback",
        "classic_bluetooth",
        "offline callback decoder for private classic-name metadata; no attachment or lookup",
        "static_apk",
        "offline_decoder",
        "private_classic_metadata",
        False,
    ),
    NonHealthCapability(
        "host_volume_state_request",
        "Host volume-state request",
        "host_integration",
        "device asks for current host volume state; the reply codec remains offline only",
        "static_apk",
        "offline_decoder",
        "host_audio_state_request",
        False,
    ),
    NonHealthCapability(
        "find_phone_alarm", "Find-phone alarm", "device_actions",
        "statically classified device action code 1; host alarm side effect blocked",
        "static_apk", "offline_decoder", "host_alarm", False,
    ),
    NonHealthCapability(
        "camera_shutter", "Camera shutter", "device_actions",
        "statically classified device action code 2", "static_apk",
        "offline_decoder", "host_camera", True,
    ),
    NonHealthCapability(
        "call_hangup", "Call hang up", "device_actions",
        "statically classified device action code 4; phone-call side effect blocked",
        "static_apk", "offline_decoder", "phone_call", False,
    ),
    NonHealthCapability(
        "weather_location_refresh", "Weather/location refresh", "device_actions",
        "statically classified device action code 5; location access blocked",
        "static_apk", "offline_decoder", "location_access", False,
    ),
    NonHealthCapability(
        "call_answer", "Call answer", "device_actions",
        "statically classified device action code 8; phone-call side effect blocked",
        "static_apk", "offline_decoder", "phone_call", False,
    ),
    NonHealthCapability(
        "media_play_pause", "Media play/pause", "device_actions",
        "statically classified device action code 16", "static_apk",
        "offline_decoder", "host_media", True,
    ),
    NonHealthCapability(
        "media_next", "Media next", "device_actions",
        "statically classified device action code 32", "static_apk",
        "offline_decoder", "host_media", True,
    ),
    NonHealthCapability(
        "media_previous", "Media previous", "device_actions",
        "statically classified device action code 64", "static_apk",
        "offline_decoder", "host_media", True,
    ),
    NonHealthCapability(
        "camera_open", "Camera open request", "device_actions",
        "statically classified device action code 65; camera lifecycle blocked",
        "static_apk", "offline_decoder", "host_camera_lifecycle", False,
    ),
    NonHealthCapability(
        "camera_close", "Camera close request", "device_actions",
        "statically classified device action code 66; camera lifecycle blocked",
        "static_apk", "offline_decoder", "host_camera_lifecycle", False,
    ),
    NonHealthCapability(
        "time_sync_request", "Time sync request", "device_actions",
        "statically classified device action code 67; device write request blocked",
        "static_apk", "offline_decoder", "device_write_request", False,
    ),
    NonHealthCapability(
        "volume_up", "Volume up", "device_actions",
        "statically classified device action code 68", "static_apk",
        "offline_decoder", "host_audio", True,
    ),
    NonHealthCapability(
        "volume_down", "Volume down", "device_actions",
        "statically classified device action code 69", "static_apk",
        "offline_decoder", "host_audio", True,
    ),
    NonHealthCapability(
        "cumulative_step_counter", "Cumulative step counter", "sensor_candidates",
        "receive-only unsigned counter; one increment is not yet a verified gesture",
        "static_apk", "offline_decoder", "cumulative_counter", False,
    ),
    NonHealthCapability(
        "unknown_motion_channels", "Nine unknown motion channels", "sensor_candidates",
        "nine signed 16-bit channels with unproven axes; reviewed app callback discards its argument",
        "static_apk", "offline_decoder", "unknown", False,
    ),
    NonHealthCapability(
        "raw_ai_actions", "Raw AI action notifications", "raw_channel",
        "bounded static framing; reviewed app callback discards its arguments; no subscription control",
        "static_apk", "offline_codec", "neutral_action_code", False,
    ),
    NonHealthCapability(
        "raw_audio_or_image_payloads", "Raw audio or image payload framing", "raw_channel",
        "bounded hidden decoder; reviewed app callback discards its arguments; no capture or output",
        "static_apk", "offline_codec", "opaque_payload", False,
    ),
)


def static_non_health_capabilities() -> tuple[NonHealthCapability, ...]:
    """Return immutable evidence descriptions without touching Bluetooth or uinput."""

    return _CAPABILITIES
