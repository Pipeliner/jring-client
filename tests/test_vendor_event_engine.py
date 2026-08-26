from jring.event_contracts import EventRelationship, NeutralEventKind
from jring.vendor_event_engine import VendorEventEngine
from jring.vendor_session_arbiter import VendorSessionArbiter


def test_only_current_unclaimed_registry_callback_becomes_neutral_event():
    arbiter = VendorSessionArbiter()
    token = arbiter.begin()
    arbiter.subscribe(token, target="main")
    arbiter.claim_transaction_callback(token, callback_id="onGetDeviceInfo")
    engine = VendorEventEngine(arbiter)
    assert engine.observe(token, callback_id="onGetDeviceInfo") is None
    assert engine.observe(token, callback_id="unknown") is None
    event = engine.observe(token, callback_id="onReceiveSensorData")
    assert event is not None
    assert event.semantic_kind is NeutralEventKind.UNKNOWN
    assert event.relationship is EventRelationship.UNKNOWN
    assert event.automation_eligible is False
