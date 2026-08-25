from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from jring.vendor_codec_registry import (
    CALLBACK_CODEC_LOCATORS,
    REQUEST_CODEC_LOCATORS,
    CodecBindingKind,
    resolve_codec_symbols,
)
from jring.vendor_coverage import (
    OFFLINE_REQUEST_CODEC_STATES,
    VendorPythonState,
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


def test_request_registry_exactly_matches_all_eighty_five_codec_rows():
    expected = {
        row.name
        for row in static_vendor_operation_coverage()
        if row.python_state in OFFLINE_REQUEST_CODEC_STATES
    }

    assert type(REQUEST_CODEC_LOCATORS) is MappingProxyType
    assert set(REQUEST_CODEC_LOCATORS) == expected
    assert len(expected) == 85


def test_callback_registry_exactly_matches_all_eighty_six_decoder_rows():
    expected = {
        row.name
        for row in static_vendor_callback_coverage()
        if row.python_state is VendorPythonState.OFFLINE_RESPONSE_CODEC
    }

    assert type(CALLBACK_CODEC_LOCATORS) is MappingProxyType
    assert set(CALLBACK_CODEC_LOCATORS) == expected
    assert len(expected) == 86


def test_every_registry_target_resolves_to_callable_code():
    for registry in (REQUEST_CODEC_LOCATORS, CALLBACK_CODEC_LOCATORS):
        for locator in registry.values():
            resolved = resolve_codec_symbols(locator)
            assert len(resolved) == len(locator.targets) >= 1
            assert all(callable(target) for target in resolved)
            assert locator.hardware_eligible is False
            assert locator.runnable is False


def test_shared_and_stateful_codecs_are_not_misrepresented_as_direct():
    assert REQUEST_CODEC_LOCATORS["setNotify"].kind is CodecBindingKind.PIPELINE
    assert REQUEST_CODEC_LOCATORS["setHeartRateMode"].kind is (
        CodecBindingKind.BRANCHING_FACTORY
    )
    expected_sensor_modes = {
        "setBloodPressureMode": "SensorSessionMode.MODE_1",
        "setSpoMode": "SensorSessionMode.MODE_2",
        "setSugarMode": "SensorSessionMode.MODE_3",
        "setPressureMode": "SensorSessionMode.MODE_4",
    }
    for name, mode in expected_sensor_modes.items():
        locator = REQUEST_CODEC_LOCATORS[name]
        assert locator.kind is CodecBindingKind.BRANCHING_FACTORY
        assert locator.targets[0].binding == (f"enabled=true:{mode}",)
        assert locator.targets[1].binding == ("enabled=false:mode_zero",)
        assert locator.limitations == ()

    assert CALLBACK_CODEC_LOCATORS["onGetWifiSsid"].kind is (
        CodecBindingKind.STATEFUL_FACTORY
    )
    expected_raw_parsers = {
        "onGetAiAction": "parse_raw_ai_action",
        "onGetRawData": "parse_raw_data",
        "onGetAiState": "parse_raw_ai_state",
        "onRecvDeviceVoiceCommandConfirm": "parse_raw_voice_command_confirmation",
        "onGetAiCommandType": "parse_raw_ai_command_type",
    }
    for name, qualname in expected_raw_parsers.items():
        locator = CALLBACK_CODEC_LOCATORS[name]
        assert locator.kind is CodecBindingKind.DIRECT_CALLABLE
        assert locator.targets[0].qualname == qualname
        assert locator.limitations == ()


def test_dial_alarm_and_language_expose_source_behavior_divergences():
    dial = REQUEST_CODEC_LOCATORS["setDeviceDialState"]
    assert dial.source_pre_enqueue_effects == (
        "set_internal_mode_flag",
        "clear_ordinary_command_queue",
        "clear_current_retained_frame",
    )
    assert dial.source_effects_reproduced is False

    alarm = REQUEST_CODEC_LOCATORS["setAlarm"]
    assert alarm.kind is CodecBindingKind.STATEFUL_FACTORY
    assert {
        "source_retained_list_not_reproduced",
        "source_sequential_enqueue_not_atomic",
        "byte_exact_for_observed_boolean_app_subset",
    } <= set(alarm.limitations)

    language = REQUEST_CODEC_LOCATORS["setLanguage"]
    assert {
        "source_no_argument_host_locale_derived",
        "python_requires_explicit_canonical_tag",
    } <= set(language.limitations)


def test_coverage_rows_link_back_to_registry_entries():
    requests = {
        row.name: row for row in static_vendor_operation_coverage()
        if row.name in REQUEST_CODEC_LOCATORS
    }
    callbacks = {
        row.name: row for row in static_vendor_callback_coverage()
        if row.name in CALLBACK_CODEC_LOCATORS
    }

    assert all(
        row.evidence_locator == f"jring.vendor_codec_registry:request:{name}"
        for name, row in requests.items()
    )
    assert all(
        row.evidence_locator == f"jring.vendor_codec_registry:callback:{name}"
        for name, row in callbacks.items()
    )

    sample = REQUEST_CODEC_LOCATORS["getDeviceInfo"]
    with pytest.raises(FrozenInstanceError):
        sample.targets = ()
    with pytest.raises(TypeError):
        REQUEST_CODEC_LOCATORS["invented"] = sample
