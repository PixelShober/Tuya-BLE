"""Tests for product-specific Tuya BLE handshake parameters."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "tuya_local_ble"
    / "tuya_ble"
    / "handshake.py"
)
SPEC = importlib.util.spec_from_file_location("handshake", MODULE_PATH)
handshake = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(handshake)


class DeviceInfoPayloadTest(unittest.TestCase):
    def test_gj635_requests_default_att_mtu(self) -> None:
        self.assertEqual(handshake.device_info_payload("laxpwq3g"), b"\x00\x14")

    def test_preserves_raykube_handshake(self) -> None:
        self.assertEqual(handshake.device_info_payload("hc7n0urm"), b"\x00\xf3")

    def test_other_products_keep_empty_payload(self) -> None:
        self.assertEqual(handshake.device_info_payload("other"), bytes(0))

    def test_gj635_uses_bounded_delayed_connection(self) -> None:
        self.assertEqual(handshake.connection_attempts("laxpwq3g"), 3)
        self.assertEqual(handshake.packet_write_delay("laxpwq3g"), 0.05)

    def test_other_products_preserve_connection_behavior(self) -> None:
        self.assertEqual(handshake.connection_attempts("other"), 100)
        self.assertEqual(handshake.packet_write_delay("other"), 0)

    def test_gj635_uses_short_connected_response_timeout(self) -> None:
        self.assertEqual(handshake.response_wait_timeout("laxpwq3g", 60), 8)
        self.assertEqual(handshake.response_wait_timeout("other", 60), 60)


if __name__ == "__main__":
    unittest.main()
