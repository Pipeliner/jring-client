"""Non-runnable evidence models for the recovered firmware-update boundaries.

The source application combines an ordinary vendor command channel, remote metadata,
mutable files, and a hardware-specific SUOTA state machine.  This module describes
that composition but intentionally provides no frame bytes, parser, file access,
network access, transport hook, or execution method.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_SERVICE_FEF5


class FirmwareAndTransferEvidenceOperation(str, Enum):
    GET_OTA_INFO = "get_ota_info"
    START_FILE_OTA = "start_file_ota"
    NOTIFY_FTP_DOWNLOAD_COMPLETED = "notify_ftp_download_completed"


@dataclass(frozen=True)
class OfflineFirmwareAndTransferSafety:
    binary_parsing: bool = False
    network_access: bool = False
    file_access: bool = False
    file_mutation: bool = False
    transport_integration: bool = False


@dataclass(frozen=True)
class MainChannelFrameEvidence:
    endpoint_uuid: str
    frame_length: int
    fixed_fields: tuple[tuple[int, int, int], ...]
    derived_fields: tuple[tuple[int, int, str], ...]
    zero_ranges: tuple[tuple[int, int], ...]
    source_enqueue_position: str
    source_clears_queue_first: bool


@dataclass(frozen=True)
class OtaPhaseEvidence:
    code: str
    boundary: str
    observation: str


@dataclass(frozen=True)
class OtaCallbackEvidence:
    name: str
    source: str
    observation: str


@dataclass(frozen=True)
class OtaBlocker:
    code: str
    boundary: str
    observation: str


_SAFETY = OfflineFirmwareAndTransferSafety()


@dataclass(frozen=True, init=False, repr=False)
class OfflineFirmwareAndTransferEvidence:
    operation: FirmwareAndTransferEvidenceOperation
    main_channel_frame: MainChannelFrameEvidence
    phases: tuple[OtaPhaseEvidence, ...]
    callbacks: tuple[OtaCallbackEvidence, ...]
    blockers: tuple[OtaBlocker, ...]
    dangerous_side_effects: tuple[str, ...]
    secondary_gatt_service_uuid: str | None
    relationship_code: str | None

    def __init__(self) -> None:
        raise TypeError("OTA evidence uses closed operation descriptions")

    @classmethod
    def _create(
        cls,
        *,
        operation: FirmwareAndTransferEvidenceOperation,
        main_channel_frame: MainChannelFrameEvidence,
        phases: tuple[OtaPhaseEvidence, ...],
        callbacks: tuple[OtaCallbackEvidence, ...],
        blockers: tuple[OtaBlocker, ...],
        dangerous_side_effects: tuple[str, ...],
        secondary_gatt_service_uuid: str | None = None,
        relationship_code: str | None = None,
    ) -> "OfflineFirmwareAndTransferEvidence":
        evidence = object.__new__(cls)
        object.__setattr__(evidence, "operation", operation)
        object.__setattr__(evidence, "main_channel_frame", main_channel_frame)
        object.__setattr__(evidence, "phases", phases)
        object.__setattr__(evidence, "callbacks", callbacks)
        object.__setattr__(evidence, "blockers", blockers)
        object.__setattr__(evidence, "dangerous_side_effects", dangerous_side_effects)
        object.__setattr__(
            evidence, "secondary_gatt_service_uuid", secondary_gatt_service_uuid
        )
        object.__setattr__(evidence, "relationship_code", relationship_code)
        return evidence

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def safety(self) -> OfflineFirmwareAndTransferSafety:
        return _SAFETY

    @property
    def evidence_scope(self) -> str:
        return "reconstructible_main_frame_and_non_runnable_workflow_evidence"

    @property
    def known_unknowns(self) -> tuple[str, ...]:
        return (
            "eligible_device_models",
            "owner_hardware_status_ordering",
            "safe_characteristic_timing",
            "complete_failure_callback_behavior",
        )

    def __repr__(self) -> str:
        return (
            "OfflineFirmwareAndTransferEvidence("
            f"operation={self.operation.value!r}, runnable=False, "
            "hardware_eligible=False, hardware_verified=False)"
        )


def _phase(code: str, boundary: str, observation: str) -> OtaPhaseEvidence:
    return OtaPhaseEvidence(code, boundary, observation)


def _callback(name: str, source: str, observation: str) -> OtaCallbackEvidence:
    return OtaCallbackEvidence(name, source, observation)


def _blocker(code: str, boundary: str, observation: str) -> OtaBlocker:
    return OtaBlocker(code, boundary, observation)


_GET_INFO_FRAME = MainChannelFrameEvidence(
    endpoint_uuid=VENDOR_CHARACTERISTIC_33F3,
    frame_length=20,
    fixed_fields=((0, 1, 0x0C),),
    derived_fields=(),
    zero_ranges=((1, 20),),
    source_enqueue_position="tail",
    source_clears_queue_first=False,
)

_START_FILE_FRAME = MainChannelFrameEvidence(
    endpoint_uuid=VENDOR_CHARACTERISTIC_33F3,
    frame_length=20,
    fixed_fields=((0, 1, 0x35),),
    derived_fields=((1, 1, "0x02 when requested OTA type is 3; otherwise 0x01"),),
    zero_ranges=((2, 20),),
    source_enqueue_position="tail",
    source_clears_queue_first=True,
)

_FTP_COMPLETED_FRAME = MainChannelFrameEvidence(
    endpoint_uuid=VENDOR_CHARACTERISTIC_33F3,
    frame_length=20,
    fixed_fields=((0, 1, 0x54), (1, 1, 0x07)),
    derived_fields=(),
    zero_ranges=((2, 20),),
    source_enqueue_position="tail",
    source_clears_queue_first=False,
)


_GET_INFO = OfflineFirmwareAndTransferEvidence._create(
    operation=FirmwareAndTransferEvidenceOperation.GET_OTA_INFO,
    main_channel_frame=_GET_INFO_FRAME,
    phases=(
        _phase(
            "main_device_info_query",
            "Bluetooth main channel",
            "Sets a pending OTA-info flag and appends the exact device-info query.",
        ),
        _phase(
            "device_info_response",
            "Bluetooth main response parser",
            "Parses device version, product identifier, and a response CRC result; the "
            "ordinary device-info callback fires before OTA metadata processing.",
        ),
        _phase(
            "metadata_cache_lookup",
            "preferences and application files directory",
            "Builds a product-derived firmware path, creates the configured directory, "
            "and reuses cached JSON while its server-provided expiry remains fresh.",
        ),
        _phase(
            "metadata_http_fetch",
            "cloud network",
            "On cache miss or expiry, starts a background plaintext HTTP GET for localized "
            "update metadata and stores a successful JSON response in preferences; the "
            "network callback invokes automatic download handling before comparison.",
        ),
        _phase(
            "eligibility_and_version_compare",
            "metadata policy",
            "Applies optional individual-device lists and compares a version component; "
            "cached metadata reaches this before download, while newly fetched metadata "
            "reaches it only after automatic download handling has been invoked.",
        ),
        _phase(
            "firmware_download_branch",
            "cloud network and application file",
            "A fresh successful metadata response downloads the firmware entity into "
            "memory and writes it to the derived path even when automatic OTA is disabled. "
            "That branch starts before device eligibility and version comparison.",
        ),
        _phase(
            "download_digest_compare",
            "application file",
            "Compares the written file with the metadata-provided MD5 text and records a "
            "cache timestamp only after a match.",
        ),
        _phase(
            "optional_start_file_ota",
            "OTA state handoff",
            "A matching automatic download enters the same hardware-specific file OTA "
            "pipeline described by the start-file operation; on the fresh-network branch "
            "this can begin before the later eligibility/version callback path.",
        ),
    ),
    callbacks=(
        _callback(
            "onGetDeviceInfo",
            "main response parser",
            "Reports parsed device fields and the response CRC result independently of "
            "the later metadata decision.",
        ),
        _callback(
            "onGetOtaInfo",
            "cache or network metadata comparator",
            "Reports available/not-available plus update JSON and the derived local path; "
            "non-200 metadata responses report not-available with empty JSON.",
        ),
        _callback(
            "onGetOtaUpdate",
            "service callback",
            "Automatic mode reports firmware-download start, busy, failure, or digest "
            "success before the hardware transfer callbacks begin.",
        ),
    ),
    blockers=(
        _blocker(
            "device_info_crc_not_an_ota_gate",
            "device response",
            "The computed response CRC is reported but does not gate metadata lookup or "
            "automatic update initiation.",
        ),
        _blocker(
            "plaintext_metadata_transport",
            "cloud metadata",
            "The statically embedded metadata endpoint uses HTTP rather than an "
            "authenticated transport.",
        ),
        _blocker(
            "unauthenticated_metadata",
            "cloud metadata",
            "No metadata signature or authenticated manifest verification is present.",
        ),
        _blocker(
            "weak_firmware_digest",
            "firmware download",
            "Firmware acceptance uses MD5 supplied by the same unauthenticated metadata.",
        ),
        _blocker(
            "unbounded_download_materialization",
            "firmware download",
            "The HTTP entity is converted to one byte array without a visible size limit.",
        ),
        _blocker(
            "info_query_can_download_firmware",
            "operation scope",
            "A fresh successful get-info metadata response initiates firmware download and "
            "file replacement even when the automatic-OTA boolean is false.",
        ),
        _blocker(
            "download_written_before_digest_acceptance",
            "application file",
            "Downloaded bytes overwrite the local path before MD5 comparison, and a "
            "mismatch is not removed in the recovered path.",
        ),
        _blocker(
            "network_auto_start_precedes_eligibility_compare",
            "metadata policy",
            "For newly fetched metadata, automatic download handling is called before "
            "individual-device eligibility and version-newer comparison; a matching "
            "download can hand off to OTA before that comparison runs.",
        ),
        _blocker(
            "network_exception_callback_gap",
            "cloud network",
            "Network helper exceptions are logged without a guaranteed OTA callback.",
        ),
        _blocker(
            "no_static_hardware_eligibility",
            "device eligibility",
            "The trace does not establish a safe product allowlist for this client.",
        ),
    ),
    dangerous_side_effects=(
        "creates an application firmware/cache directory",
        "writes metadata and timestamp preferences",
        "downloads an unbounded entity into memory",
        "overwrites an application firmware file before digest acceptance",
        "may automatically enter the device firmware-update pipeline",
    ),
)


_START_FILE = OfflineFirmwareAndTransferEvidence._create(
    operation=FirmwareAndTransferEvidenceOperation.START_FILE_OTA,
    main_channel_frame=_START_FILE_FRAME,
    secondary_gatt_service_uuid=VENDOR_SERVICE_FEF5,
    phases=(
        _phase(
            "resolve_current_device",
            "platform Bluetooth adapter",
            "Resolves the service's current device address and replaces the prior OTA "
            "controller with a new stateful controller.",
        ),
        _phase(
            "clear_queue_and_request_mode",
            "Bluetooth main channel",
            "Clears the ordinary vendor command queue, then appends the exact mode-change "
            "frame described by this evidence model.",
        ),
        _phase(
            "delayed_secondary_gatt_connect",
            "platform Bluetooth stack",
            "After a fixed delay, opens another GATT connection to the selected device.",
        ),
        _phase(
            "discover_suota_and_enable_status",
            "SUOTA GATT service",
            "Refreshes/discovers services, requires the SUOTA characteristic set, and "
            "writes its status CCCD before transfer.",
        ),
        _phase(
            "open_and_materialize_firmware",
            "caller-selected local file",
            "Allocates the stream's reported available length and performs one unchecked "
            "read into that byte array.",
        ),
        _phase(
            "append_xor_check_byte",
            "firmware preparation",
            "Appends one byte equal to the XOR of all original firmware bytes.",
        ),
        _phase(
            "configure_suota_transfer",
            "SUOTA GATT service",
            "Writes memory-device, GPIO-map, and patch-length controls using fixed source "
            "configuration plus negotiated MTU and patch-size values.",
        ),
        _phase(
            "stream_no_response_chunks",
            "SUOTA patch-data characteristic",
            "Partitions the in-memory image into blocks and chunks, then performs direct "
            "write-without-response firmware writes while broadcasting progress.",
        ),
        _phase(
            "consume_status_notifications",
            "GATT callback and local broadcasts",
            "Characteristic writes and SUOTA status notifications advance the state "
            "machine or map device/library failures to broadcast errors.",
        ),
        _phase(
            "end_reboot_disconnect_cleanup",
            "SUOTA controls and platform Bluetooth stack",
            "Writes end and conditional reboot signals, releases the wake lock, closes "
            "the file, disconnects/closes GATT, and may refresh the GATT cache.",
        ),
    ),
    callbacks=(
        _callback(
            "onGetOtaUpdate",
            "service callback",
            "Reports a transfer-start status before the firmware file is opened and "
            "forwards distinct progress percentages from a broadcast receiver.",
        ),
        _callback(
            "SUOTA status and write callbacks",
            "GATT callback",
            "Service discovery, CCCD completion, characteristic completion, MTU changes, "
            "and status notifications drive internal steps.",
        ),
        _callback(
            "OTA progress and terminal actions",
            "broadcast receiver",
            "Progress is forwarded to the service callback; proceeding and success "
            "actions trigger transfer configuration and cleanup respectively.",
        ),
    ),
    blockers=(
        _blocker(
            "caller_controlled_file_path",
            "local file",
            "The public binder operation accepts the firmware path directly.",
        ),
        _blocker(
            "unvalidated_ota_type",
            "mode selection",
            "The binder accepts any integer OTA type; equality with one special value "
            "changes the initial mode frame, while another value controls the later reboot.",
        ),
        _blocker(
            "no_preflight_file_validation",
            "local file",
            "The start operation does not establish existence, type, size, digest, "
            "signature, or model compatibility before changing device mode.",
        ),
        _blocker(
            "success_callback_precedes_file_open",
            "service callback",
            "A transfer-start callback uses the source's success status before file open "
            "and parser preparation, so it cannot prove readiness.",
        ),
        _blocker(
            "firmware_fully_materialized_in_memory",
            "firmware preparation",
            "The complete caller-selected file is allocated and read before chunking.",
        ),
        _blocker(
            "unchecked_single_file_read",
            "firmware preparation",
            "The parser sizes from available(), performs one read, and ignores the returned "
            "byte count before treating the buffer as the firmware image.",
        ),
        _blocker(
            "xor_byte_is_not_authenticity",
            "firmware preparation",
            "The appended XOR byte detects only limited corruption and provides no "
            "authenticity or model binding.",
        ),
        _blocker(
            "hardware_specific_suota_state_machine",
            "SUOTA GATT service",
            "Correctness depends on undocumented device transitions, characteristic "
            "semantics, timing, negotiated sizes, and status ordering.",
        ),
        _blocker(
            "gpio_selector_same_tool_divergence",
            "SUOTA configuration",
            "Structured and fallback decompiler modes disagree on selector packing and "
            "write control flow; no selector meaning is accepted without bounded "
            "instruction review.",
        ),
        _blocker(
            "dormant_custom_dial_transfer_no_interface_call_site",
            "SDK surface separation",
            "A distinct custom-dial transfer implementation has no observed construction "
            "or interface call site; the ordinary editDeviceDialCustom request neither "
            "models nor authorizes dial-file transfer.",
        ),
        _blocker(
            "write_without_response_chunk_stream",
            "SUOTA patch-data characteristic",
            "Firmware chunks use direct no-response writes; safe pacing and delivery have "
            "not been validated on eligible hardware.",
        ),
        _blocker(
            "coarse_progress_integer_division",
            "progress reporting",
            "Block progress divides integers before conversion to a percentage, so the "
            "reported value is effectively coarse rather than reliable chunk progress.",
        ),
        _blocker(
            "ota_error_callback_gap",
            "error reporting",
            "The SUOTA manager emits a dedicated error broadcast that the recovered "
            "service receiver does not register alongside its progress action.",
        ),
        _blocker(
            "no_terminal_success_service_callback",
            "completion reporting",
            "The recovered SUOTA success action invokes reboot/disconnect cleanup but does "
            "not emit a final success through onGetOtaUpdate.",
        ),
        _blocker(
            "no_static_hardware_eligibility",
            "device eligibility",
            "Runtime SUOTA-service discovery is not a model allowlist or safe eligibility "
            "proof for this client.",
        ),
    ),
    dangerous_side_effects=(
        "clears the ordinary command queue",
        "changes device firmware-update mode",
        "opens a second GATT connection",
        "may refresh the platform GATT cache",
        "reads the complete caller-selected firmware file",
        "writes firmware chunks to SUOTA characteristics",
        "may reboot and disconnect the device",
    ),
)


_FTP_COMPLETED = OfflineFirmwareAndTransferEvidence._create(
    operation=FirmwareAndTransferEvidenceOperation.NOTIFY_FTP_DOWNLOAD_COMPLETED,
    main_channel_frame=_FTP_COMPLETED_FRAME,
    phases=(
        _phase(
            "ftp_terminal_signal",
            "media-file FTP workflow",
            "The source emits this frame after its separate FTP success path and after "
            "terminal FTP failure once retries are exhausted.",
        ),
    ),
    callbacks=(
        _callback(
            "onNotifyFtpStateInfo",
            "service callback",
            "Reports the independent FTP transfer result after the terminal signal.",
        ),
    ),
    blockers=(
        _blocker(
            "not_an_ota_completion_signal",
            "workflow relationship",
            "The call belongs to media-file FTP synchronization, not firmware download "
            "verification, SUOTA completion, or reboot cleanup.",
        ),
    ),
    dangerous_side_effects=(
        "signals completion of a separate device FTP/media workflow",
    ),
    relationship_code="ftp_media_boundary_not_firmware_ota",
)


def evidence_for(
    operation: FirmwareAndTransferEvidenceOperation,
) -> OfflineFirmwareAndTransferEvidence:
    if type(operation) is not FirmwareAndTransferEvidenceOperation:
        raise TypeError("operation must be a FirmwareAndTransferEvidenceOperation")
    return {
        FirmwareAndTransferEvidenceOperation.GET_OTA_INFO: _GET_INFO,
        FirmwareAndTransferEvidenceOperation.START_FILE_OTA: _START_FILE,
        FirmwareAndTransferEvidenceOperation.NOTIFY_FTP_DOWNLOAD_COMPLETED: _FTP_COMPLETED,
    }[operation]
