# Capturing the GJ-635 BLE handshake with an Android HCI snoop log

Goal: record exactly what the Smart Life / Tuya app writes to the lock and what
the lock notifies back, so the real handshake for this firmware can be decoded.
Everything the integration needs is in that capture.

Target for reference while reading the log:

- Lock MAC: `XX:XX:XX:XX:XX:XX`
- Service: `0000a201-0000-1000-8000-00805f9b34fb`
- Write characteristic (app → lock): `00002b11-...`
- Notify characteristic (lock → app): `00002b10-...`

## What you need

- An Android phone (Android 9 or newer is fine).
- The **Smart Life** or **Tuya Smart** app, with **this lock already added** to
  it and working over Bluetooth (able to unlock from the app while nearby).
- A computer with `adb` (Android platform-tools) for pulling the log. On the
  phone this is the only reliable no-root method on modern Android.

## Step 1 — Enable Developer Options

1. Settings → About phone.
2. Tap **Build number** seven times until it says "You are now a developer".
3. Go back to Settings → System → **Developer options**.

## Step 2 — Turn on the Bluetooth HCI snoop log

1. In Developer options, find **Enable Bluetooth HCI snoop log** (may be under a
   "Networking" or "Debugging" subsection; search "snoop" in Settings search).
2. Set it to **Enabled** (some phones offer "Filtered"/"Full" — pick **Full**).
3. **Toggle Bluetooth off and back on.** The snoop log only starts recording
   after a Bluetooth restart, so this step is required.

## Step 3 — Reproduce the handshake cleanly

Keep it short so the log is easy to read:

1. Force-close the Smart Life / Tuya app first (so the next open triggers a
   fresh BLE connect).
2. Stand next to the lock with the phone.
3. Note the wall-clock time, then open the app and go to the lock.
4. Let it connect, then **unlock and lock once** over Bluetooth. Wait for the app
   to confirm each action.
5. Note the time again. A 20–30 second capture is plenty.

Avoid doing anything else Bluetooth-heavy on the phone during this window (fewer
unrelated devices = cleaner log).

## Step 4 — Pull the log off the phone

On modern Android the snoop file lives in `/data/misc/bluetooth/logs/` and is not
directly readable without root. The reliable no-root way is a bug report, which
bundles it:

1. Connect the phone by USB, enable **USB debugging** in Developer options,
   accept the RSA prompt.
2. On the computer:

   ```
   adb bugreport gj635-capture
   ```

   This writes `gj635-capture.zip`.
3. Inside the zip, the capture is at:

   ```
   FS/data/misc/bluetooth/logs/btsnoop_hci.log
   ```

   (there may also be a `btsnoop_hci.log.last` — grab both if present).

If your phone is rooted, you can skip the bug report and pull it directly:

```
adb root
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log
```

Some phones instead expose **Developer options → Take bug report**, which saves
the same zip and lets you share it without a computer.

## Step 5 — Hand it to me

Put the `btsnoop_hci.log` (and `.last` if present) somewhere I can read it, e.g.:

```
/home/pixel/Dokumente/Projects/Home Assistant/Tuya-BLE/captures/
```

Tell me the two timestamps you noted. **Do not commit it** — add the file, tell
me the path, and I will parse it. The capture contains this lock's real BLE
traffic; the credentials in it are already known to us, but it stays out of git.

## What I do with it

I load it in Wireshark / a btsnoop parser, filter to `XX:XX:XX:XX:XX:XX`, and
read:

- the exact bytes the app writes to `2b11` for its first `DEVICE_INFO`-style
  frame (header, protocol version, payload, fragmentation),
- what the lock notifies back on `2b10` (this is the reply we never get),
- the order of frames before the unlock (any hello / time-sync / pairing step
  we are missing).

That tells us precisely how this firmware differs from the standard handshake,
which is the one thing guesswork cannot give us.

## Optional: turn the snoop log back off

When you are done, set **Enable Bluetooth HCI snoop log** back to **Disabled**
and toggle Bluetooth once, so the phone stops logging all BLE traffic.

## Result 2026-07-11: Samsung bugreport is not enough

Both the on-device "Bug report" and `adb bugreport` on this Samsung phone
(bootloader locked, `verifiedbootstate green`, no working `su`) only include
`FS/data/log/bt/btsnooz_hci.log`, never the full `btsnoop_hci.log`. `btsnooz`
is a lossy ring-buffer snapshot: decoding it (8-byte records
`len16 LE / ts32 LE / type16 LE`, then `len` bytes, `0x20`=command `0x10`=event)
gave 817 packets that are **all HCI commands and events, zero ACL data**. The
lock MAC does appear in the LE-meta connection events, so the app did connect —
but the GATT writes and notifications we need ride in ACL payloads, which
`btsnooz` drops. The full `btsnoop_hci.log` (with ACL) lives at
`/data/misc/bluetooth/logs/` and is root-only; a locked Samsung will not give it
up through a bugreport.

Working alternatives to get the ATT data:

- **External BLE sniffer** (nRF52840 dongle + nRF Sniffer for Bluetooth LE +
  Wireshark): capture the app↔lock connection over the air. The ATT writes are
  the Tuya frames; they are AES-encrypted with `md5(local_key[:6])`, which we
  have, so they can be decrypted after capture. Most reliable.
- **A rootable / already-rooted Android**: pull
  `/data/misc/bluetooth/logs/btsnoop_hci.log` directly after reproducing.
- **Samsung `*#9900#` SysDump**: may export a fuller BT log on some models;
  unverified here.
