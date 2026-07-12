"""Helpers for reassembling fragmented Tuya BLE notifications."""

from __future__ import annotations


def append_fragment_payload(
    buffer: bytearray,
    payload: bytes | bytearray,
    expected_length: int,
) -> bytes:
    """Append frame bytes and return padding beyond the declared length.

    Some locks send every notification at the full ATT payload size, including
    the final fragment.  The frame length in fragment zero remains authoritative;
    bytes after that length are transport padding and must not invalidate the
    otherwise complete encrypted frame.
    """
    remaining = max(expected_length - len(buffer), 0)
    buffer += payload[:remaining]
    return bytes(payload[remaining:])
