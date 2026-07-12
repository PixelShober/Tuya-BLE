# Claude handout: GJ-635 Tuya BLE current state

Date: 2026-07-12
Repo: `/home/pixel/Dokumente/Projects/Home Assistant/Tuya-BLE`
Branch: `feat/gj635-laxpwq3g`

This is the short handoff for continuing the GJ-635APP+KEY (`laxpwq3g`) local
BLE work. Do not include device secrets, HA tokens, passwords, or captured
device-specific DP 71 command bytes in committed files or chat summaries.

## Current status

- Latest local commit: `a4a9b62 Quiet recoverable notification reassembly artifacts`.
- Key commits: `7f595fb` (padded fragments), `c0af021` (real BLE secret in
  devices.json local_key), `a4a9b62` (reassembly noise → debug).
- QA `192.168.178.181`: config entry `loaded`, and on 2026-07-12 during a
  supervised operation **battery DP 8 was read live at 73%** over the local BLE
  session (also DP 13 and DP 69 parsed cleanly). Notification error spam is gone
  from the system log after `a4a9b62`.
- DP 19 (bluetooth unlock record) still `unknown` — needs a real BLE unlock
  event, not just manual operation.
- `ble_unlock_check` (for `lock_control`) NOT yet added to QA. Best source is the
  prod `devices.json`, but prod SSH `192.168.178.165` is currently blocked
  (Bitwarden agent locked → `Permission denied (publickey)`). Decoding it from
  `captures/btfull.log` with the recovered session key is the fallback.
- Prod/live Home Assistant at `192.168.178.165` was only inspected and should
  not be changed until QA proves the full lock path.
- QA config entry: `GJ-635APP+KEY 0236FF`, entry id
  `01KX9T1G840D87SXFQ6JJGY8DJ`.
- QA entities after load:
  - `sensor.gj_635app_key_0236ff_battery`: `unknown`
  - `sensor.gj_635app_key_0236ff_bluetooth_unlock_record`: `unknown`
  - `lock.gj_635app_key_0236ff_lock_control`: `unavailable`

## Proven facts

- The original handshake blocker was not the GATT handle or Tuya frame shape.
  The lock needs a device-specific 6-byte BLE secret.
- The integration works when that BLE secret is stored in `devices.json` as
  `local_key`, because this code derives the Tuya BLE login/session keys from
  `local_key[:6]`.
- The cloud `local_key` is not the BLE secret for this lock.
- The padded-notification issue is fixed locally:
  - New helper: `custom_components/tuya_local_ble/tuya_ble/fragment.py`
  - Main change: `tuya_ble.py` now trims final fragments to the frame length
    declared in fragment zero instead of feeding trailing ATT padding into the
    decrypt/parse path.
  - Test: `tests/test_fragment.py`
- Unit tests passed after the fragment fix.
- A temporary QA diagnostic proved a multi-fragment encrypted reply reassembled
  and parsed as DP 69 with raw length 3.
- The diagnostic code and marker were removed again; QA was redeployed with the
  clean committed code.

## Why `lock_control` is unavailable

There are two separate states:

1. The lock entity is disabled by default intentionally. In `lock.py`, the
   profile sets `entity_registry_enabled_default=False` for safety.
2. If the user enables it manually, it can still be `unavailable`. For command
   locks, `TuyaBLELock.available` requires `self._device.ble_unlock_check`.
   QA `devices.json` currently has the BLE login key but no `ble_unlock_check`.

So this is not evidence that the integration failed to load. It means the
command path is still gated because the device-specific DP 71 check value is
missing.

## Datapoint mapping

- DP 8: Battery. Smart Life capture showed value `73`, but only after an unlock
  sequence. The lock may not send this during plain setup.
- DP 19: Bluetooth unlock record. Also appeared after the unlock sequence.
- DP 69: Accessory record retrieval request. QA proved we can now parse this
  after the fragment-padding fix.
- DP 70: Accessory pairing.
- DP 71: Lock/unlock command path. Requires device-specific command/check data.
- DP 72: Records/report path after command activity.

## Do not do blindly

- Do not trigger unlock/lock commands unless the user is physically at the lock
  and explicitly confirms the supervised test.
- Do not remove or weaken the existing cloud fallback until local BLE unlock is
  proven end to end.
- Do not push changes to prod `192.168.178.165` before QA succeeds.
- Do not commit secrets from Frida logs, `devices.json`, HA tokens, SSH
  passwords, or raw device-specific DP 71 payloads.

## Next steps

1. With the user physically at the lock, wake or manually operate the lock and
   inspect QA for DP 8 and DP 19 updates.
2. Add the captured device-specific `ble_unlock_check` to QA `devices.json`.
   This should make `lock_control` available after reload/restart.
3. Implement the DP 69 response using the central id, peripheral id, and pairing
   random values recovered from the accepted pairing/session flow.
4. Run exactly one supervised DP 71 unlock test on QA, then inspect:
   - command response
   - DP 19 unlock record
   - DP 72 records/reporting
   - battery DP 8 behavior
5. Only after QA proves the local BLE path, copy the required safe changes to
   prod `192.168.178.165`.
6. Push the branch and open a PR or otherwise preserve the fork state, because a
   HACS reinstall/update can overwrite direct deployed files.

## Useful files

- `docs/gj635-handshake-capture-analysis.md`: full analysis and proof trail.
- `docs/frida-hook-setup.md`: Frida setup used to recover the BLE secret.
- `custom_components/tuya_local_ble/tuya_ble/fragment.py`: padding-aware
  fragment helper.
- `tests/test_fragment.py`: regression coverage for the real padded fragment
  shape.
