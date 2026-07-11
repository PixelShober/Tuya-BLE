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

The request is very likely dropped before it is ever processed. The next probe
writes with a response so that the lock has to report an ATT error instead of
staying silent; an authentication or encryption error there would mean the lock
requires a bonded link, which an ESPHome proxy cannot provide. A wrong login key
would produce the same silence, so the credentials remain a suspect as well.

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
