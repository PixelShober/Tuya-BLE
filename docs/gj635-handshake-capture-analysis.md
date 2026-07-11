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

## What this means

The GJ-635 is not a standard Tuya BLE lock at the crypto layer. Making it work
locally requires replicating the `0x001a`/`0x001d` challenge/response and the
key it derives, which the packet capture alone does not reveal — it would need
the algorithm from the Smart Life app (APK analysis) or Tuya's newer jtmspro BLE
spec. That is a separate, substantial reverse-engineering effort.

Pragmatic alternative: control the lock through the Tuya cloud / a gateway,
which works today with the verified credentials and needs none of this.

## Reproduce the decode

`captures/btfull.log` (gitignored) + tshark:

```
tshark -r captures/btfull.log -Y 'bthci_acl.chandle==0x0041 && btatt' \
  -T fields -e frame.number -e hci_h4.direction -e btatt.opcode \
  -e btatt.handle -e btatt.uuid16 -e btatt.value
```
