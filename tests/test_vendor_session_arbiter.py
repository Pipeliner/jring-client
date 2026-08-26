import pytest

from jring.vendor_session_arbiter import ArbiterRoute, ArbiterToken, VendorSessionArbiter


def test_one_generation_owns_each_subscription_and_transaction_callback_once():
    arbiter = VendorSessionArbiter(maximum_neutral_events=2)
    token = arbiter.begin()
    arbiter.subscribe(token, target="main")
    arbiter.subscribe(token, target="raw")
    with pytest.raises(RuntimeError, match="duplicate_subscription"):
        arbiter.subscribe(token, target="main")
    arbiter.claim_transaction_callback(token, callback_id="onGetDeviceInfo")
    assert arbiter.route_callback(token, callback_id="onGetDeviceInfo") is ArbiterRoute.TRANSACTION
    assert arbiter.route_callback(token, callback_id="onReceiveSensorData") is ArbiterRoute.NEUTRAL_EVENT
    assert arbiter.route_callback(token, callback_id="onReceiveSensorData") is ArbiterRoute.NEUTRAL_EVENT
    assert arbiter.route_callback(token, callback_id="onReceiveSensorData") is ArbiterRoute.OVERFLOW


def test_stale_forged_and_closed_tokens_cannot_route_or_reopen_connection():
    arbiter = VendorSessionArbiter()
    first = arbiter.begin()
    arbiter.subscribe(first, target="main")
    arbiter.close(first)
    assert arbiter.route_callback(first, callback_id="x") is ArbiterRoute.CLOSED
    second = arbiter.begin()
    assert arbiter.route_callback(first, callback_id="x") is ArbiterRoute.STALE
    with pytest.raises(TypeError, match="owned"):
        ArbiterToken()
    with pytest.raises(ValueError, match="stale_or_forged"):
        arbiter.subscribe(first, target="main")
    arbiter.close(second)
