# Frida hook to recover the GJ-635 session key

Goal: watch the Smart Life app's crypto at runtime while it unlocks the lock,
so we can see the key and plaintext of the pre-handshake (`0x001a`/`0x001d`
challenge/response) and the `DEVICE_INFO` frame — the thing packet captures
alone cannot give us. Runtime hooking bypasses the app's obfuscation.

## Already set up (rooted SM-S908B, arm64)

- `frida-server` 17.15.4 pushed to `/data/local/tmp/frida-server`, runs as root.
- `frida-tools` 17.15.4 in the session venv on the PC.
- Hook script: `tools/frida-tuya-hook.js` — logs every Java AES/HMAC/MD5 op with
  key, IV, input and output as hex.

Restart frida-server if the phone rebooted:

```
adb shell su -c "setsid /data/local/tmp/frida-server </dev/null >/dev/null 2>&1 &"
frida-ps -U        # should list processes
```

## Capture procedure

The lock re-runs the full handshake on every unlock (it drops the idle BLE link
after ~25 s), so attaching to the running app and then unlocking is enough — no
need to spawn.

1. On the phone, open the **Smart Life** app instance that has the lock. If the
   lock lives in the **Secure Folder** (user 150 on this phone), open that copy.
   Navigate to the lock's page but do not unlock yet.
2. Attach the hook (frida-server runs as root, so it reaches either user):

   ```
   frida -U -n com.tuya.smartlife -l tools/frida-tuya-hook.js -o crypto.log
   ```

   Wait for `[*] Tuya crypto hooks installed.`
3. **Unlock the lock from the app**, wait for confirmation, then lock again.
4. Stop frida (Ctrl+D). The crypto operations are in `crypto.log`.

## What we look for

In `crypto.log`, correlate with `captures/btfull.log`:

- an `[AES]` whose `in` or `out` matches the pre-handshake bytes
  `ca2d25e65e90e24de03ad9e320c45dcb` (write to `0x001a`) or its reply
  `080cf642835cd2a556e4936052091392` — the `[KEY]` line just before it is the
  key that handshake uses;
- an `[AES]` whose plaintext, once found, reveals the `DEVICE_INFO` structure
  and the session-key derivation;
- `[HASH]` MD5 lines show any `md5(...)` key derivation (upstream uses
  `md5(local_key[:6])`; we will see what this firmware actually hashes).

If nothing shows up, the crypto is in a native `.so` (not the Java layer). Then
the next step is hooking the native AES in the Tuya security library
(`library`/`libtostitch`/BoringSSL `AES_*`) — a follow-up script.

## Cleanup

```
adb shell su -c "pkill -f frida-server"
adb shell su -c "rm -f /data/local/tmp/frida-server"
```
