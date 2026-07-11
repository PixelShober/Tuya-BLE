# GJ-635APP+KEY (`laxpwq3g`)

Experimental local BLE support for the GJ-635APP+KEY smart lock.

## Confirmed device data

- Category: `jtmspro`
- Product ID: `laxpwq3g`
- Tested module firmware: `4.4`
- Advertised service: `0000a201-0000-1000-8000-00805f9b34fb`
- Battery: DP 8 (`residual_electricity`)
- Bluetooth unlock record: DP 19 (`unlock_ble`)
- Accessory pairing: DP 70 (`check_code_set`)
- Lock/unlock command: DP 71 (`ble_unlock_check`)

## Safety status

The product profile, battery sensor, DP 19 diagnostic sensor, and DP 71 payload
builder are implemented. The lock entity is disabled by default until a local,
supervised hardware test confirms the command and response behavior.

DP 70 is not treated as a per-command challenge. Tuya documents it as the
central/peripheral pairing exchange that establishes the IDs and eight-byte
random value used by DP 71. The integration therefore derives each DP 71
request from the device-specific reported value, swaps the direction-specific
IDs, preserves the paired random value, and generates a fresh timestamp. It
does not replay a captured unlock packet.

Reference: [Tuya Bluetooth lock data point reference](https://developer.tuya.com/en/docs/iot/ble?id=K9ow3vcpn71ua)

## Connection status

The lock never answers a `DEVICE_INFO` request. Setup therefore fails with
`timeout receiving response` on every attempt and the config entry stays in
`setup_error`. Waking the lock by pressing its keypad during setup does not
change this.

What the live tests through an ESPHome Bluetooth proxy have established:

- The GATT connection is accepted at about `-72 dBm`, and the lock exposes the
  standard Tuya profile: `2b10` (`notify`) and `2b11` (`write-without-response`,
  `write`). Subscribing to notifications succeeds.
- The request is written, no notification of any kind arrives, and the lock
  drops the connection a few seconds later.
- The framing is not the cause. Payload (empty and `00 14`), header protocol
  version (advertised V3 and V2) and fragment size (20-byte ATT default and a
  single 244-byte write) were probed in every combination against the hardware.
  All six timed out identically.
- The advertisement carries service data for `0000a201` but no Tuya
  manufacturer data, so the bind flag and the encrypted device UUID cannot
  always be read from it.

- Writing the request with a response, so that the lock has to acknowledge or
  reject it at the ATT layer, produced no error. The lock accepts the bytes and
  then ignores them, so it does not require a bonded link and the ESPHome proxy
  is not the limitation.

Everything below the Tuya protocol layer therefore works: the link, the
characteristics, the write and the subscription. The lock receives a
well-formed frame, acknowledges it, and refuses to act on it.

The credentials are also confirmed correct. The `local_key`, `uuid`
(`node_id`) and `device_id` in `devices.json` were compared byte for byte
against the Tuya IoT cloud record for this device and match exactly, and the
cloud MAC matches the advertised address. A wrong login key is therefore ruled
out, so the request the lock ignores is both well-framed and correctly
encrypted.

What this leaves:

- The subscription may not deliver notifications through this ESPHome proxy at
  all. Nothing has ever confirmed a notification arriving from this lock, so the
  next step is to prove the notify path works (any inbound frame), independently
  of the handshake.
- The `jtmspro` door-lock firmware may not use the standard `DEVICE_INFO`
  handshake and may expect the accessory pairing flow (DP 70) or a wake/hello
  sequence first.
- The cloud shows the lock as `online: false` with `residual_electricity: 62`,
  so it is a healthy BLE-only device with no always-on gateway; its radio only
  wakes for a short window on physical interaction.

## Notify probe and handshake comparison (2026-07-11)

A diagnostic that connects, subscribes and idles was run three times while the
lock was physically operated inside the listening window (confirmed operation
until 20:47:35 during the 20:47:26–20:47:53 window). Every run behaved the same:

- The lock accepts the connection, then disconnects itself after ~25 s of an
  idle link. It does not tolerate a connection without a prompt valid handshake.
- No notification ever arrived on `2b10`, not even while the lock was being
  operated. The lock therefore appears to emit nothing before its session is
  authenticated, so the notify probe cannot by itself separate a broken notify
  path from a lock that stays mute pre-auth.

The `DEVICE_INFO` handshake is confirmed identical to the working reference.
ShonP40/Tuya-BLE drives the A1 Pro Max (`rlyxv7pe`, also `jtmspro`) with the
same service UUID `0000a201`, the same `2b10`/`2b11` characteristics, and the
same empty-payload standard `DEVICE_INFO` followed by `PAIR` — with no
per-product special case (its product entry is only `name="A1 PRO MAX"`). Our
connect flow shares that upstream commit. That lock replies to those exact
bytes; the GJ-635 does not. The silence is a device/firmware difference, not a
code gap that copying a working integration can close.

## Only remaining avenue: capture a real handshake

The GJ-635 (`laxpwq3g`) is not covered by any published integration, and it does
not answer the handshake that a sibling `jtmspro` lock accepts. The definitive
next step is to capture what this specific lock actually expects: enable the
Android HCI snoop log, open the Smart Life / Tuya app next to the lock, let it
connect and unlock over BLE, then pull `btsnoop_hci.log` and inspect the frames
it writes to `2b11` and the notifications it receives on `2b10`. That shows the
real handshake for this firmware; everything short of it is guesswork.

## Deployment trap

The integration is installed through HACS from `PixelShober/Tuya-BLE`, and the
GJ-635 work only exists locally. Any HACS download of the repository replaces
`/config/custom_components/tuya_local_ble` with the published branch and removes
`handshake.py` and `lock_protocol.py`. This happened once mid-test and made a
probe run report results from the upstream code. Re-deploy the working tree
after any HACS action, or push the branch before relying on HACS.

## Required `devices.json` fields

```json
{
  "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<device UUID>",
    "local_key": "<device local key>",
    "device_id": "<device ID>",
    "category": "jtmspro",
    "product_id": "laxpwq3g",
    "device_name": "DoorLock",
    "product_model": "GJ-635APP+KEY",
    "product_name": "GJ-635APP+KEY",
    "ble_unlock_check": "<base64 raw Tuya DP 71 status value>"
  }
}
```

Keep this file at `/config/tuya_local_ble/devices.json`. Never commit it.

## Supervised test order

1. Confirm the BLE address with an advertisement or Smart Life trace.
2. Load the integration and verify DP 8 without enabling the lock entity.
3. Trigger a manual Bluetooth unlock and confirm DP 19 updates.
4. Enable the disabled lock entity locally.
5. Test one unlock while physically present at the door.
6. Confirm the DP 71 response and retry behavior before testing repeated use.
