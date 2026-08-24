import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("JRING_HARDWARE_TEST") != "1",
    reason="requires explicitly selected JRing hardware",
)


def test_hardware_opt_in_marker():
    assert os.environ.get("JRING_DEVICE_ADDRESS"), "explicit address required"
