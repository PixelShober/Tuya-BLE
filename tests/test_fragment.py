"""Tests for Tuya BLE notification reassembly helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "tuya_local_ble"
    / "tuya_ble"
    / "fragment.py"
)
SPEC = importlib.util.spec_from_file_location("fragment", MODULE_PATH)
fragment = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(fragment)


class AppendFragmentPayloadTest(unittest.TestCase):
    def test_trims_padding_from_real_gj635_status_fragments(self) -> None:
        # Fragment headers removed: fragment zero declares a 33-byte encrypted
        # frame, while fragment one is padded to a full 19-byte ATT payload.
        first_payload = bytes.fromhex(
            "053f7a7245c57d6b8c8ab85fabedeb2662"
        )
        second_payload = bytes.fromhex(
            "5c9b5b5f72fd143b6b9fbc9bd70cbfb0779f40"
        )
        buffer = bytearray()

        self.assertEqual(
            fragment.append_fragment_payload(buffer, first_payload, 33),
            b"",
        )
        padding = fragment.append_fragment_payload(buffer, second_payload, 33)

        self.assertEqual(len(buffer), 33)
        self.assertEqual(padding, bytes.fromhex("779f40"))

    def test_keeps_normal_fragment_unchanged(self) -> None:
        buffer = bytearray(b"abc")

        padding = fragment.append_fragment_payload(buffer, b"def", 6)

        self.assertEqual(buffer, b"abcdef")
        self.assertEqual(padding, b"")


if __name__ == "__main__":
    unittest.main()
