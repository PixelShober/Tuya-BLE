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
