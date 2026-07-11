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
# dataclass() resolves the module from sys.modules, so register it first.
sys.modules["handshake"] = handshake
SPEC.loader.exec_module(handshake)


class HandshakeVariantTest(unittest.TestCase):
    def test_gj635_probes_a_write_with_response_first(self) -> None:
        first = handshake.handshake_variant("laxpwq3g", 0)
        self.assertTrue(first.write_with_response)
        self.assertEqual(first.payload, bytes(0))
        self.assertEqual(first.chunk_mtu, 20)

    def test_gj635_falls_back_to_upstream_framing(self) -> None:
        self.assertEqual(handshake.handshake_variant("laxpwq3g", 1),
                         handshake.STANDARD)
        self.assertEqual(handshake.handshake_variant("laxpwq3g", 99),
                         handshake.STANDARD)

    def test_preserves_raykube_handshake(self) -> None:
        variant = handshake.handshake_variant("hc7n0urm", 0)
        self.assertEqual(variant.payload, b"\x00\xf3")
        self.assertEqual(variant.header_version, 2)
        self.assertEqual(variant.chunk_mtu, 244)

    def test_other_products_keep_upstream_framing(self) -> None:
        variant = handshake.handshake_variant("other", 7)
        self.assertEqual(variant.payload, bytes(0))
        self.assertIsNone(variant.header_version)
        self.assertEqual(variant.chunk_mtu, 20)

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
