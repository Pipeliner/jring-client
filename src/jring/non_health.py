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
        "camera_shutter", "Camera shutter", "device_actions",
        "statically classified device action code 2", "static_apk",
        "offline_decoder", "host_camera", True,
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
        "nine signed 16-bit channels with unproven axes and gesture semantics",
        "static_apk", "offline_decoder", "unknown", False,
    ),
    NonHealthCapability(
        "raw_ai_actions", "Raw AI action notifications", "raw_channel",
        "bounded static request and response framing; no subscription control",
        "static_apk", "offline_codec", "neutral_action_code", False,
    ),
    NonHealthCapability(
        "raw_audio_or_image_payloads", "Raw audio or image payload framing", "raw_channel",
        "bounded hidden payload decoder; no capture, streaming, or local output",
        "static_apk", "offline_codec", "opaque_payload", False,
    ),
)


def static_non_health_capabilities() -> tuple[NonHealthCapability, ...]:
    """Return immutable evidence descriptions without touching Bluetooth or uinput."""

    return _CAPABILITIES
