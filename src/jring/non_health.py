"""Local-only inventory of statically supported non-health capability evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, init=False, repr=False)
class NonHealthCapability:
    name: str
    label: str
    group: str
    description: str
    evidence: str
    maturity: str
    meaning: str
    input_candidate: bool
    privacy_classes: tuple[str, ...]
    request_operations: tuple[str, ...]
    callback_operations: tuple[str, ...]
    runnable: bool
    hardware_eligible: bool
    hardware_verified: bool
    live_available: bool
    input_eligible: bool
    scripted_fake_decoder_available: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("non-health capability rows are closed")

    def __repr__(self) -> str:
        return f"<closed non-health capability {self.name!r}>"


def _capability(
    name: str,
    label: str,
    group: str,
    description: str,
    evidence: str,
    maturity: str,
    meaning: str,
    input_candidate: bool,
    *,
    privacy: tuple[str, ...] = ("not_applicable",),
    requests: tuple[str, ...] = (),
    callbacks: tuple[str, ...] = (),
    scripted_fake_decoder_available: bool = False,
) -> NonHealthCapability:
    row = object.__new__(NonHealthCapability)
    resolved_privacy = (
        ("user_intent",)
        if group == "device_actions" and privacy == ("not_applicable",)
        else privacy
    )
    for field_name, value in {
        "name": name,
        "label": label,
        "group": group,
        "description": description,
        "evidence": evidence,
        "maturity": maturity,
        "meaning": meaning,
        "input_candidate": input_candidate,
        "privacy_classes": tuple(resolved_privacy),
        "request_operations": tuple(requests),
        "callback_operations": tuple(callbacks),
        "runnable": False,
        "hardware_eligible": False,
        "hardware_verified": False,
        "live_available": False,
        "input_eligible": False,
        "scripted_fake_decoder_available": scripted_fake_decoder_available,
    }.items():
        object.__setattr__(row, field_name, value)
    return row


_CAPABILITIES = (
    _capability(
        "standard_hid_metadata",
        "Standard HID metadata",
        "standard_metadata",
        "metadata inventory surface available only after explicit device selection; this local list observes no device and reads no report values",
        "bluetooth_standard",
        "selected_device_metadata",
        "standard_hid",
        False,
    ),
    _capability(
        "classic_profile_attachment",
        "Classic profile attachment",
        "classic_bluetooth",
        "Android bond/profile/socket attachment plumbing; separate from vendor GATT and not a HID capability",
        "static_apk",
        "offline_behavior_evidence",
        "platform_plumbing",
        False,
    ),
    _capability(
        "classic_rfcomm_socket_lifecycle",
        "Classic RFCOMM socket lifecycle reference",
        "classic_bluetooth",
        "embedded OTA helper constructs and closes a classic socket; no connect, read, or write is observed, and actual OTA transfer uses GATT",
        "static_apk",
        "offline_behavior_evidence",
        "socket_lifecycle_reference",
        False,
    ),
    _capability(
        "classic_bt_info_callback",
        "Classic Bluetooth info callback",
        "classic_bluetooth",
        "offline callback decoder and exact scripted fake preserve two neutral non-identifier values without classic attachment",
        "static_apk",
        "offline_decoder",
        "classic_metadata",
        False,
        callbacks=("onNotifyClassicBtInfo",),
        scripted_fake_decoder_available=True,
    ),
    _capability(
        "classic_bt_name_callback",
        "Classic Bluetooth name callback",
        "classic_bluetooth",
        "offline callback decoder and exact scripted fake redact private classic-name metadata; no attachment or lookup",
        "static_apk",
        "offline_decoder",
        "private_classic_metadata",
        False,
        privacy=("device_name",),
        callbacks=("onNotifyClassicBtName",),
        scripted_fake_decoder_available=True,
    ),
    _capability(
        "host_volume_state_request",
        "Host volume-state request",
        "host_integration",
        "device asks for current host volume state; a separate fake-only coordinator exercises one closed caller-supplied offline projection without reading host audio",
        "static_apk",
        "offline_decoder",
        "host_audio_state_request",
        False,
        privacy=("host_audio_state_request",),
        requests=("sendPhoneVolume",),
        callbacks=("onGetPhoneVolume",),
        scripted_fake_decoder_available=True,
    ),
    _capability(
        "find_phone_alarm", "Find-phone alarm", "device_actions",
        "statically classified device action code 1; host alarm side effect blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "camera_shutter", "Camera shutter", "device_actions",
        "statically classified device action code 2", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "call_hangup", "Call hang up", "device_actions",
        "statically classified device action code 4; phone-call side effect blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "weather_location_refresh", "Weather/location refresh", "device_actions",
        "statically classified device action code 5; location access blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "call_answer", "Call answer", "device_actions",
        "statically classified device action code 8; phone-call side effect blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "media_play_pause", "Media play/pause", "device_actions",
        "statically classified device action code 16", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "media_next", "Media next", "device_actions",
        "statically classified device action code 32", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "media_previous", "Media previous", "device_actions",
        "statically classified device action code 64", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "camera_open", "Camera open request", "device_actions",
        "statically classified device action code 65; camera lifecycle blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "camera_close", "Camera close request", "device_actions",
        "statically classified device action code 66; camera lifecycle blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "time_sync_request", "Time sync request", "device_actions",
        "statically classified device action code 67; device write request blocked",
        "static_apk", "offline_decoder", "unverified_static_action_code", False,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "volume_up", "Volume up", "device_actions",
        "statically classified device action code 68", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "volume_down", "Volume down", "device_actions",
        "statically classified device action code 69", "static_apk",
        "offline_decoder", "unverified_static_action_code", True,
        callbacks=("onGetDeviceAction",), scripted_fake_decoder_available=True,
    ),
    _capability(
        "cumulative_step_counter", "Cumulative step counter", "sensor_candidates",
        "receive-only unsigned counter; one increment is not yet a verified gesture",
        "static_apk", "offline_decoder", "cumulative_counter", False,
        privacy=("activity_count",),
        callbacks=("onGetSportSteps",),
        scripted_fake_decoder_available=True,
    ),
    _capability(
        "unknown_motion_channels", "Nine unknown motion channels", "sensor_candidates",
        "nine signed 16-bit channels with unproven axes; reviewed app callback discards its argument",
        "static_apk", "offline_decoder", "unknown", False,
        privacy=("motion_sensor_data",),
    ),
    _capability(
        "raw_ai_actions", "Raw AI action notifications", "raw_channel",
        "bounded static framing; reviewed app callback discards its arguments; no subscription control",
        "static_apk", "offline_codec", "neutral_action_code", False,
        privacy=("neutral_action_code",),
        requests=("connectAiServerNotification", "setAiExtraAction"),
        callbacks=("onGetAiAction",),
    ),
    _capability(
        "raw_audio_or_image_payloads", "Raw audio or image payload framing", "raw_channel",
        "bounded hidden decoder; reviewed app callback discards its arguments; no capture or output",
        "static_apk", "offline_codec", "opaque_payload", False,
        privacy=("audio_or_image_content",),
        requests=("openAiAudioState",),
        callbacks=("onGetRawData",),
    ),
    _capability(
        "main_chatgpt_action", "Main-channel ChatGPT action", "general_use",
        "offline decoder preserves one neutral action value; chat execution and content handling are unavailable",
        "static_apk", "offline_codec", "neutral_action_code", False,
        privacy=("neutral_action_code",),
        requests=("setAiChatState", "setChatgptContent"),
        callbacks=("onGetChatgptAction",),
    ),
    _capability(
        "offline_speech_mode", "Offline speech-recognition mode", "general_use",
        "offline query, setting, and response codecs; microphone access and speech execution are unavailable",
        "static_apk", "offline_codec", "speech_setting", False,
        privacy=("speech_setting",),
        requests=(
            "queryOfflineSpeechRecognitionState",
            "setOfflineSpeechRecognitionState",
        ),
        callbacks=("onGetOfflineSpeechRecognitionMode",),
    ),
    _capability(
        "raw_ai_state", "Raw AI state", "general_use",
        "bounded raw-channel state commands and response decoder; notification subscription remains unavailable",
        "static_apk", "offline_codec", "ai_state", False,
        privacy=("ai_state",),
        requests=("openAiState", "queryAiState"),
        callbacks=("onGetAiState",),
    ),
    _capability(
        "raw_ai_command_type", "Raw AI command type", "general_use",
        "bounded raw-channel command-type request and response decoder with neutral integer meaning",
        "static_apk", "offline_codec", "neutral_command_type", False,
        privacy=("ai_command",),
        requests=("setAiCommandType",),
        callbacks=("onGetAiCommandType",),
    ),
    _capability(
        "raw_voice_command_confirmation", "Raw voice-command confirmation", "general_use",
        "bounded raw-channel confirmation decoder; it captures neither audio nor recognized text",
        "static_apk", "offline_decoder", "neutral_confirmation_code", False,
        privacy=("voice_command_state",),
        callbacks=("onRecvDeviceVoiceCommandConfirm",),
    ),
    _capability(
        "wifi_state", "Wi-Fi state", "general_use",
        "offline decoder preserves a neutral device Wi-Fi state code; no network access is performed",
        "static_apk", "offline_decoder", "network_state", False,
        privacy=("network_state",),
        callbacks=("onGetWifiState",),
    ),
    _capability(
        "wifi_ssid_inventory", "Wi-Fi SSID inventory", "general_use",
        "offline scan request plus count and ordered-fragment decoders; network names are never stored in this inventory",
        "static_apk", "offline_stateful_codec", "network_inventory", False,
        privacy=("network_identifier",),
        requests=("scanWifi",),
        callbacks=("onGetWifiSsid", "onGetWifiSsidCount"),
    ),
    _capability(
        "wifi_ap_state", "Wi-Fi access-point state", "general_use",
        "offline AP-state and hotspot request evidence; network identifiers and credentials remain private and no network is joined",
        "static_apk", "offline_codec", "network_access_point", False,
        privacy=("network_identifier", "network_credential"),
        requests=(
            "openWifiApMode",
            "setWifiHotSpotInfo",
            "setWifiHotSpotInfoEx",
        ),
        callbacks=("onDeviceConnectedWifi", "onNotifyDeviceWifiApState"),
    ),
    _capability(
        "device_system_state", "Device-system state", "general_use",
        "offline query and notification decoder preserve a neutral state value",
        "static_apk", "offline_codec", "device_state", False,
        privacy=("device_state",),
        requests=("getDeviceSystemStateInfo",),
        callbacks=("onNotifyDeviceSystemStateInfo",),
    ),
    _capability(
        "eq_profile", "Equalizer profile", "general_use",
        "offline get/set codecs preserve signed profile values; host audio is not changed",
        "static_apk", "offline_codec", "audio_profile", False,
        privacy=("audio_profile",),
        requests=("getEqInfo", "setEqInfo2"),
        callbacks=("onGetEqInfo2", "onSetEqInfo2"),
    ),
    _capability(
        "media_file_state", "Media-file state", "general_use",
        "offline device file-state decoder and separate media-file callback evidence; file references are never retained here",
        "static_apk", "offline_codec", "media_file_state", False,
        privacy=("file_reference",),
        requests=("getMediaFileState",),
        callbacks=("onGetDeviceFileState", "onNotifyNewMediaInfo"),
    ),
    _capability(
        "device_dial_metadata", "Device dial metadata", "general_use",
        "offline dial query and metadata decoders; no file download, transfer, or device mutation is available",
        "static_apk", "offline_codec", "device_personalization", False,
        privacy=("device_personalization", "cloud_content"),
        requests=(
            "getDeviceDial",
            "setDeviceDialState",
            "setDeviceWallpaperState",
        ),
        callbacks=(
            "onGetDeviceDial",
            "onNotifyDialJsonContent",
            "onSetDeviceDialState",
            "onSetDeviceWallpaperState",
        ),
    ),
    _capability(
        "device_dial_custom", "Custom dial state", "general_use",
        "offline custom-dial query, state, and acknowledgement codecs; transfer side effects are not reproduced",
        "static_apk", "offline_codec", "device_personalization", False,
        privacy=("device_personalization",),
        requests=("getDeviceDialCustom", "editDeviceDialCustom"),
        callbacks=("onEditDeviceDialCustom", "onGetDeviceDialCustom"),
    ),
    _capability(
        "touch_mode", "Touch mode", "general_use",
        "offline setting and response codecs preserve a neutral mode value",
        "static_apk", "offline_codec", "touch_setting", False,
        privacy=("touch_setting",),
        requests=("setTouchMode",),
        callbacks=("onGetTouchMode",),
    ),
    _capability(
        "screen_light_time", "Screen-light time", "general_use",
        "offline setting and response codecs preserve a neutral duration value",
        "static_apk", "offline_codec", "display_setting", False,
        privacy=("display_setting",),
        requests=("SetScreenLightTime",),
        callbacks=("onGetScreenLightTime",),
    ),
)


def static_non_health_capabilities() -> tuple[NonHealthCapability, ...]:
    """Return immutable evidence descriptions without touching Bluetooth or uinput."""

    from .vendor_callback_surfaces import recovered_callback_behavior_surfaces
    from .vendor_codec_registry import (
        CALLBACK_CODEC_LOCATORS,
        REQUEST_CODEC_LOCATORS,
    )

    callback_names = set(CALLBACK_CODEC_LOCATORS) | {
        row.name for row in recovered_callback_behavior_surfaces()
    }
    missing_requests = {
        operation
        for capability in _CAPABILITIES
        for operation in capability.request_operations
        if operation not in REQUEST_CODEC_LOCATORS
    }
    missing_callbacks = {
        operation
        for capability in _CAPABILITIES
        for operation in capability.callback_operations
        if operation not in callback_names
    }
    if missing_requests or missing_callbacks:
        raise RuntimeError("non-health inventory operation link is stale")
    return _CAPABILITIES
