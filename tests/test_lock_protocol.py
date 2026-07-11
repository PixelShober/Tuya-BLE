"""Tests for the dependency-free smart-lock protocol helpers."""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "tuya_local_ble"
    / "lock_protocol.py"
)
SPEC = importlib.util.spec_from_file_location("lock_protocol", MODULE_PATH)
lock_protocol = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lock_protocol)


class BuildAccessoryLockPayloadTest(unittest.TestCase):
    def test_builds_fresh_unlock_request_from_report(self) -> None:
        reported = bytes.fromhex(
            "0001ffff313233343536373801010203040000"
        )

        payload = lock_protocol.build_accessory_lock_payload(
            base64.b64encode(reported).decode(),
            unlock=True,
            timestamp=0x11223344,
        )

        self.assertEqual(
            payload,
            bytes.fromhex("ffff0001313233343536373801112233440001"),
        )

    def test_builds_lock_request(self) -> None:
        reported = bytes.fromhex(
            "0001ffff313233343536373801010203040000"
        )

        payload = lock_protocol.build_accessory_lock_payload(
            reported,
            unlock=False,
            timestamp=0,
        )

        self.assertEqual(payload[12], 0)
        self.assertEqual(payload[13:17], bytes(4))

    def test_rejects_unpaired_random_value(self) -> None:
        reported = bytes.fromhex(
            "0001ffff000000000000000001010203040000"
        )

        with self.assertRaisesRegex(ValueError, "unpaired"):
            lock_protocol.build_accessory_lock_payload(reported, unlock=True)

    def test_rejects_invalid_base64(self) -> None:
        with self.assertRaisesRegex(ValueError, "base64"):
            lock_protocol.build_accessory_lock_payload("not base64", unlock=True)


if __name__ == "__main__":
    unittest.main()
