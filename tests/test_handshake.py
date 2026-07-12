"""Tests for product-specific Tuya BLE handshake parameters."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
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
sys.modules["handshake"] = handshake
SPEC.loader.exec_module(handshake)


class HandshakeVariantTest(unittest.TestCase):
    def test_gj635_uses_standard_framing(self) -> None:
        # The lock speaks the standard empty-payload handshake once the login
        # key (local_key[:6] = the device's own BLE secret) is correct.
        v = handshake.handshake_variant("laxpwq3g", 0)
        self.assertEqual(v, handshake.STANDARD)
        self.assertEqual(v.payload, bytes(0))
        self.assertIsNone(v.header_version)
        self.assertEqual(v.chunk_mtu, 20)
        self.assertFalse(v.write_with_response)

    def test_preserves_raykube_handshake(self) -> None:
        v = handshake.handshake_variant("hc7n0urm", 0)
        self.assertEqual(v.payload, b"\x00\xf3")
        self.assertEqual(v.header_version, 2)
        self.assertEqual(v.chunk_mtu, 244)

    def test_other_products_keep_upstream_framing(self) -> None:
        v = handshake.handshake_variant("other", 7)
        self.assertEqual(v.payload, bytes(0))
        self.assertIsNone(v.header_version)
        self.assertEqual(v.chunk_mtu, 20)

    def test_connection_and_write_tuning(self) -> None:
        self.assertEqual(handshake.connection_attempts("laxpwq3g"), 3)
        self.assertEqual(handshake.connection_attempts("other"), 100)
        self.assertEqual(handshake.packet_write_delay("laxpwq3g"), 0.05)
        self.assertEqual(handshake.response_wait_timeout("laxpwq3g", 60), 8)


if __name__ == "__main__":
    unittest.main()
