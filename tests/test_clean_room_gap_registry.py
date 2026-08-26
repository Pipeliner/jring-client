from dataclasses import FrozenInstanceError

import pytest

from jring.clean_room_gap_registry import (
    CleanRoomGap,
    CleanRoomGapDisposition,
    clean_room_gap_payload,
    recovered_clean_room_gaps,
)


def test_every_published_clean_room_gap_has_a_specific_owned_disposition():
    rows = recovered_clean_room_gaps()
    assert len(rows) == len({row.identifier for row in rows}) == 12
    assert {row.disposition for row in rows} == set(CleanRoomGapDisposition)
    assert all(row.specification.startswith("APK_") and row.tracker_issue > 0 for row in rows)
    assert clean_room_gap_payload()["complete"] is False


def test_gap_rows_are_closed_and_do_not_claim_unreviewed_completion():
    row = recovered_clean_room_gaps()[0]
    with pytest.raises(TypeError, match="closed"):
        CleanRoomGap()
    with pytest.raises(FrozenInstanceError):
        row.tracker_issue = 48
