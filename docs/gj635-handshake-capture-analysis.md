# GJ-635 (`laxpwq3g`) — decoded BLE handshake, root cause

Capture: full `btsnoop_hci.log` (with ACL) pulled from a rooted Android running
the Smart Life app, connection handle `0x0041` to `DC:23:52:02:36:FF`. Decoded
with tshark + a pycryptodome script. This is the real handshake the lock
accepts, versus the one our integration sends.

## The lock's GATT (matches ours)

Service `0x1910` at handles `0x0007-0x000c`:

- `0x0009` = characteristic `2b11` — write (app → lock)
- `0x000b` = characteristic `2b10` — notify (lock → app)
- `0x000c` = CCCD `2902` for `2b10`

These are the same characteristics our integration already uses, so the write
target is not the problem.

## Root cause: a secure pre-handshake we never perform

The app does a challenge/response on **separate** characteristics before it ever
touches the Tuya service, then sends `DEVICE_INFO`:

```
4082  read 2a00 (device name)
4087  write 16 bytes -> handle 0x001a      ca2d25e65e90e24de03ad9e320c45dcb
4089  indicate 16 bytes <- handle 0x001a   080cf642835cd2a556e4936052091392
4092  write 16 bytes -> handle 0x001d      5583fc1431d34cfb842d5be6cb2c84ae
4095  indicate 16 bytes <- handle 0x001d   6998838b3c4ae320e590f782f6c685a8
4097  enable CCCD 0x0069
4103  enable CCCD 0x006f
...
4682  enable CCCD 0x000c (for 2b10)
4690  write -> 0x0009 (2b11)  frag0: 00 21 20 04 c974feb7a77a147954320ce4a91b831b
4691  write -> 0x0009 (2b11)  frag1: 01 420d257fdc630ce0432b4cdafcb0dff8
4693  notify <- 0x000b (2b10) frag0: 00 71 30 04 44b71c07... (7 fragments, reply)
```

The two 16-byte write/indicate pairs on `0x001a` and `0x001d` are AES-block
sized and look like a session-key negotiation. Our integration, ShonP40,
PlusPlus and every other standard Tuya BLE integration skip this entirely and
jump straight to the `DEVICE_INFO` write.

## The DEVICE_INFO is not decryptable with the standard key

The reassembled `DEVICE_INFO` write is a normal Tuya frame shape:

- fragment headers stripped -> `security_flag=0x04`, `IV(16)`, `ciphertext(16)`
- total length `0x21` (33) matches, protocol byte `0x20` (V2) on the request,
  `0x30` (V3) on the reply.

Security flag `0x04` means "encrypted with the login key" in the Tuya BLE SDK,
i.e. `login_key = md5(local_key[:6])`. Decrypting either the request or the
7-fragment reply with that key (and with `md5(local_key)`, the raw key, and
uuid/device-id derivations, under prepended/zero/key IVs, checked by CRC and by
the `code==0x0000` field) yields only garbage. The credentials are the verified
cloud values, so the key itself is right — the **derivation** the lock expects
is not the standard one.

Taken together: this firmware gates the Tuya protocol behind a secure
pre-handshake, and the `DEVICE_INFO` payload is encrypted with a key that is not
`md5(local_key[:6])`. That is exactly why the lock accepts our GATT write at the
ATT layer (it did in the earlier probes) and then silently ignores it — it
cannot decrypt a frame that skipped the pre-handshake and used the wrong key.

## SOLVED — the login key is a different secret than the cloud local_key

Hooking the Smart Life app with Frida (see `docs/frida-hook-setup.md`) while it
unlocked over BLE captured the crypto in the Java layer. The decisive finding:

- The app's `DEVICE_INFO` is a normal empty Tuya frame
  (`00000001 00000000 0000 0000 <crc> 0000`) — identical to what we send.
- The login key it uses is `md5(secret6)` where `secret6` is a device-specific
  **6-byte BLE secret that is NOT the first six bytes of the cloud `local_key`**.
  The captured PAIR request confirmed it: it carries `uuid` + `secret6` +
  `device_id`, exactly where the protocol puts `local_key[:6]`.
- The session key is `md5(secret6 + srand)`, `srand` taken from the
  `DEVICE_INFO` response — which is exactly what this integration already does
  with `local_key[:6]`.

So no code change is needed for the crypto. The fix is to put the real BLE
secret in `devices.json` as `local_key`, so that `local_key[:6]` equals
`secret6`. The integration then derives the right login and session keys, builds
the right PAIR request, and the handshake completes.

Recovering `secret6` needs the Frida hook once per device (its origin — a
separate cloud field vs. a transform of the cloud key — was not pinned down; the
cloud `/v1.0/devices/{id}` `local_key` is a different value). The 6-byte secret
is stored only in `devices.json` (gitignored), never committed.

### Verified working

With the corrected `local_key`, a live test on a Home Assistant instance with an
ESPHome Bluetooth proxy in range took the config entry from `setup_error` to
`loaded`: the lock now accepts our `DEVICE_INFO`, the session establishes, and
it replies with session-key-encrypted (`security_flag 0x05`) frames.

Notification reassembly was also corrected for locks that pad the final ATT
notification beyond the encrypted frame length declared in fragment zero. A
live QA run then reassembled and parsed DP 69 successfully. Battery can still
remain `unknown` after setup because this firmware does not send DP 8 on every
connection; it populated as 73 in the Smart Life capture only after an unlock
sequence caused the lock to push it.

The lock entity is disabled by default as a deliberate safety measure. If a
user enables it, it remains unavailable until the device-specific DP 71 status
value is stored as `ble_unlock_check` in `devices.json`; the BLE login secret
alone is not enough to construct an authenticated lock command.

## Reproduce the decode

`captures/btfull.log` (gitignored) + tshark:

```
tshark -r captures/btfull.log -Y 'bthci_acl.chandle==0x0041 && btatt' \
  -T fields -e frame.number -e hci_h4.direction -e btatt.opcode \
  -e btatt.handle -e btatt.uuid16 -e btatt.value
```
