import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_notify import (
    NotifyDisposition,
    NotifyPlannerState,
    NotifyRequest,
    plan_notify,
)


def _frame(*prefix: int, payload: bytes = b"") -> bytes:
    encoded = bytes(prefix) + payload
    return encoded + bytes(20 - len(encoded))


def test_plans_exact_header_title_and_content_frames_without_live_side_effects():
    state = NotifyPlannerState.initial()
    request = NotifyRequest.create(
        notification_id="event-1",
        category=7,
        title="Title",
        content="a" * 20,
    )

    plan = plan_notify(state, request)

    assert plan.disposition is NotifyDisposition.PLANNED
    assert plan.total_frames == 4
    assert plan.internal_uid == "0000"
    assert plan.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert plan.synthetic_frames_for_test() == (
        _frame(0x12, 4, 1, 0, 7, payload=b"0000"),
        _frame(0x12, 4, 2, payload=b"Title"),
        _frame(0x12, 4, 3, payload=b"a" * 17),
        _frame(0x12, 4, 4, payload=b"a" * 3),
    )


def test_empty_content_still_has_one_content_frame():
    plan = plan_notify(
        NotifyPlannerState.initial(),
        NotifyRequest.create(
            notification_id="event-empty", category=0, title="", content=""
        ),
    )

    assert plan.total_frames == 3
    assert plan.synthetic_frames_for_test() == (
        _frame(0x12, 3, 1, 0, 0, payload=b"0000"),
        _frame(0x12, 3, 2),
        _frame(0x12, 3, 3),
    )


def test_duplicate_id_is_a_noop_and_does_not_consume_internal_uid():
    first_request = NotifyRequest.create(
        notification_id="same-id", category=1, title="first", content="private"
    )
    first = plan_notify(NotifyPlannerState.initial(), first_request)
    duplicate = plan_notify(
        first.proposed_state_after_atomic_enqueue,
        NotifyRequest.create(
            notification_id="same-id", category=2, title="changed", content="changed"
        ),
    )
    next_plan = plan_notify(
        duplicate.proposed_state_after_atomic_enqueue,
        NotifyRequest.create(
            notification_id="different-id", category=2, title="next", content="next"
        ),
    )

    assert duplicate.disposition is NotifyDisposition.DEDUPLICATED
    assert duplicate.total_frames == 0
    assert duplicate.internal_uid is None
    assert duplicate.synthetic_frames_for_test() == ()
    assert (
        duplicate.proposed_state_after_atomic_enqueue
        == first.proposed_state_after_atomic_enqueue
    )
    assert next_plan.internal_uid == "0001"


def test_internal_uid_cycles_after_source_equivalent_9998_boundary():
    state = NotifyPlannerState.synthetic_for_test(
        next_uid=9998, last_notification_id="previous"
    )
    last = plan_notify(
        state,
        NotifyRequest.create(
            notification_id="last", category=0, title="", content=""
        ),
    )
    wrapped = plan_notify(
        last.proposed_state_after_atomic_enqueue,
        NotifyRequest.create(
            notification_id="wrapped", category=0, title="", content=""
        ),
    )

    assert last.internal_uid == "9998"
    assert wrapped.internal_uid == "0000"


@pytest.mark.parametrize("category", [-1, 256, True, 1.5, "1"])
def test_rejects_categories_that_do_not_fit_the_recovered_wire_byte(category):
    exception = TypeError if type(category) is not int else ValueError
    with pytest.raises(exception):
        NotifyRequest.create(
            notification_id="id", category=category, title="", content=""
        )


@pytest.mark.parametrize("notification_id", [None, "", 1])
def test_rejects_broken_or_ambiguous_notification_ids(notification_id):
    with pytest.raises((TypeError, ValueError)):
        NotifyRequest.create(
            notification_id=notification_id, category=1, title="", content=""
        )


def test_rejects_title_truncation_and_accepts_exact_utf8_boundary():
    exact = NotifyRequest.create(
        notification_id="id", category=1, title="é" * 8 + "x", content=""
    )
    assert plan_notify(NotifyPlannerState.initial(), exact).total_frames == 3

    with pytest.raises(ValueError, match="17"):
        NotifyRequest.create(
            notification_id="id", category=1, title="é" * 9, content=""
        )


def test_content_limit_is_derived_from_one_byte_total_and_sequence_fields():
    largest = plan_notify(
        NotifyPlannerState.initial(),
        NotifyRequest.create(
            notification_id="largest", category=1, title="", content="x" * 4301
        ),
    )
    assert largest.total_frames == 255
    assert largest.synthetic_frames_for_test()[-1][0:3] == bytes((0x12, 255, 255))

    with pytest.raises(ValueError, match="4301"):
        NotifyRequest.create(
            notification_id="too-large", category=1, title="", content="x" * 4302
        )


@pytest.mark.parametrize("field", ["title", "content", "notification_id"])
def test_rejects_unpaired_surrogates(field):
    values = dict(notification_id="id", category=1, title="title", content="content")
    values[field] = "\ud800"
    with pytest.raises(ValueError):
        NotifyRequest.create(**values)


def test_request_state_plan_and_frames_do_not_retain_or_render_private_text():
    request = NotifyRequest.create(
        notification_id="private-id", category=4, title="private-title", content="secret"
    )
    plan = plan_notify(NotifyPlannerState.initial(), request)

    assert not hasattr(request, "notification_id")
    assert not hasattr(request, "title")
    assert not hasattr(request, "content")
    assert "private-id" not in repr(request)
    assert "private-title" not in repr(request)
    assert "secret" not in repr(request)
    assert "private-id" not in repr(plan.proposed_state_after_atomic_enqueue)
    assert "private-title" not in repr(plan)
    assert "secret" not in repr(plan)
    assert "707269766174652d7469746c65" not in repr(plan)
    assert "title_bytes" not in repr(request)
    assert "content_bytes" not in repr(request)
    assert "total_frames" not in repr(plan)
    assert "internal_uid" not in repr(plan)
    assert "category" not in repr(request)
    assert "next_uid" not in repr(plan.proposed_state_after_atomic_enqueue)

    different_category = NotifyRequest.create(
        notification_id="another", category=99, title="title", content="content"
    )
    advanced = NotifyPlannerState.synthetic_for_test(next_uid=9876)
    assert "99" not in repr(different_category)
    assert "9876" not in repr(advanced)


@pytest.mark.parametrize(
    "unsafe",
    ["line\nbreak", "escape\x1b", "right\u202eto-left", "zero\u200bwidth", "e\u0301"],
)
def test_notification_text_rejects_controls_formatting_and_ambiguous_unicode(unsafe):
    with pytest.raises(ValueError):
        NotifyRequest.create(
            notification_id="id", category=1, title=unsafe, content="content"
        )


def test_offline_safety_metadata_names_live_blockers_and_source_privacy_bugs():
    plan = plan_notify(
        NotifyPlannerState.initial(),
        NotifyRequest.create(
            notification_id="id", category=1, title="title", content="content"
        ),
    )

    assert plan.maturity == "static_apk_only"
    assert plan.hardware_verified is False
    assert plan.hardware_eligible is False
    assert plan.parity_scope == "offline_sequence_and_dedup_only"
    assert plan.safety.transport_integration is False
    assert plan.safety.models_caller_throttle is False
    assert plan.safety.models_acknowledgement is False
    assert plan.safety.allows_partial_send is False
    assert plan.safety.planner_state_retains_raw_notification_data is False
    assert plan.safety.plan_contains_private_wire_payload is True
    assert plan.safety.logs_raw_notification_data is False
    assert plan.safety.live_acknowledgement_has_global_overlap_race is True
    assert plan.safety.live_effect == "wearable_notification_display"
    assert plan.known_live_blockers == (
        "atomic_multi_frame_delivery",
        "acknowledgement_and_overlap_serialization",
        "caller_throttle_policy",
        "planner_state_serialization",
        "commit_only_after_atomic_delivery",
    )


def test_planning_does_not_commit_state_and_parallel_plans_conflict_explicitly():
    state = NotifyPlannerState.initial()
    request = NotifyRequest.create(
        notification_id="same", category=1, title="title", content="content"
    )

    first = plan_notify(state, request)
    retry_without_commit = plan_notify(state, request)

    assert first.internal_uid == retry_without_commit.internal_uid == "0000"
    assert first.disposition is retry_without_commit.disposition is NotifyDisposition.PLANNED
    assert "planner_state_serialization" in first.known_live_blockers
    assert not hasattr(first, "next_state")


def test_notification_id_digest_is_keyed_per_planner_and_input_is_bounded():
    request = NotifyRequest.create(
        notification_id="1", category=1, title="title", content="content"
    )
    first = plan_notify(NotifyPlannerState.initial(), request)
    second = plan_notify(NotifyPlannerState.initial(), request)

    assert (
        first.proposed_state_after_atomic_enqueue._last_notification_digest
        != second.proposed_state_after_atomic_enqueue._last_notification_digest
    )
    with pytest.raises(ValueError, match="256"):
        NotifyRequest.create(
            notification_id="x" * 257, category=1, title="title", content="content"
        )


def test_closed_types_prevent_arbitrary_frames_or_state():
    with pytest.raises(TypeError):
        NotifyRequest()
    with pytest.raises(TypeError):
        NotifyPlannerState()
