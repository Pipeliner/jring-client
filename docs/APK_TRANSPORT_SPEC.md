# Clean-room APK Bluetooth transport specification

Status: exact static route/reference inventory; runtime peripheral behavior and
secondary-route semantics remain unknown.

## Ordinary vendor routes

| Route | Service | TX | RX | Static direction |
|---|---|---|---|---|
| MAIN | `56ff` | `33f3` | `33f4` | TX write; RX notify |
| raw | `56ff` | `33f5` | `33f6` | TX write; RX notify |

The SDK’s deterministic MAIN builders use queue type `0`; raw builders use queue type
`1`. The static source roles do not establish on-device instance multiplicity,
properties, MTU, notification acceptance, direction confirmation, or model/firmware
availability.

This APK contract specifies the recovered phone-side discovery, ordering, timeout,
retry, stale-object, reconnect, and cleanup behavior below. Peripheral-owned instance
multiplicity, properties, accepted write mode, negotiated MTU, actual CCCD behavior,
and model/firmware availability remain explicit runtime unknowns.

## Other UUID families

| Family | Static fact | Remaining unknowns |
|---|---|---|
| `ffe5` / `ffe9` | service/TX constants only | no reference beyond constant initialization in this build; direction, activation, model, and runtime use are unknown |
| `57ff` | display-map label only | no executable call site established in this build; dynamic/dependency/runtime activation not excluded |
| `fef5` | executable SUOTA service | role table below; device eligibility and delivery semantics unresolved |
| `180a` | standard Device Information service; characteristics `2a23`–`2a2a` and `2a50` are statically referenced | per-model exposure and value availability |
| `180d` / `2a37` | standard Heart Rate references | per-model exposure and notification behavior |
| `2902` | standard CCCD reference | exact instance, write result, and peripheral acknowledgement |

## Android direct-instruction inventory

Counts are methods/classes with direct executable references in the complete reviewed
owned scope. Application and embedded-SDK populations are disjoint; category rows can
overlap and must not be summed into a unique-method total.

| Category | Application | Embedded SDK | Boundary |
|---|---:|---:|---|
| MTU | 1 / 1 | 2 / 2 | semantics/runtime unverified |
| connection priority | 0 / 0 | 1 / 1 | app absence is owned-scope direct-reference absence only |
| remote RSSI | 0 / 0 | 2 / 2 | Android callback status handling specified separately |
| service discovery | 3 / 2 | 3 / 3 | success does not prove required endpoints |
| RFCOMM socket | 2 / 1 | 2 / 1 | construct/close only; no owned connect/read/write observed |
| classic profiles | 11 / 3 | 0 / 0 | profile state is separate from vendor binding/HID |
| bonding | 6 / 6 | 0 / 0 | Android OS bond is separate from vendor binding |
| classic discovery | 1 / 1 | 0 / 0 | runtime behavior unverified |
| legacy LE scan | 9 / 3 | 1 / 1 | SDK reference has no start/stop reference |
| modern LE scan | 0 / 0 | 7 / 2 | app absence is not an unsupported claim |
| descriptor-write setup | 6 / 3 | 6 / 4 | submission/callback/peripheral acknowledgement are distinct |
| notification setup | 2 / 1 | 3 / 2 | activation return is not CCCD acknowledgement |
| characteristic read | 1 / 1 | 1 / 1 | target/value semantics per call site remain required |
| characteristic write | 6 / 1 | 9 / 2 | dynamic and queued writes are separate paths |
| GATT connect lifecycle | 5 / 5 | 11 / 7 | shared object/generation and teardown races remain |
| adapter power | 2 / 2 | 2 / 2 | platform action, not peripheral capability |

Descriptor reads, PHY selection, LE advertising, L2CAP channels, GATT-server role, and
Android HID-device role each have zero direct references in both owned scopes. This is
`absent-in-owned-scope`, not proof of unsupported behavior in dependencies, dynamic
code, firmware, or the physical ring.

## Scan and selection behavior

The SDK scan Binder call is accepted only while the shared SDK status equals 200 and
returns that status either way. It resets the reconnect-scan counter but does not
validate Android permission. A requested state equal to the SDK's remembered scan flag
is ignored.

Starting creates an empty modern `ScanFilter`, passes the caller-selected scan-mode
integer to `ScanSettings.Builder`, and uses `BluetoothLeScanner.startScan`. The mode is
stored without validation, so an invalid value can fail while constructing settings.
A missing scanner is logged, but the SDK still marks its lower-level scan-running flag
true. A ten-second task stops the Android scan; a separate 15-second task increments a
counter and attempts to call the same requested state. Because the remembered
high-level state remains true after the ten-second stop, that restart call is ignored.
Consequently a later `scanDevice(true)` is also ignored until a false request resets
the high-level flag. Scan failure is logged without an application callback, and batch
results are ignored.

For each individual result the SDK reads the device, RSSI, and raw scan-record bytes.
It first applies an advertisement predicate, derives a local name with device-name
fallback, extracts a nine-byte vendor field, and calls `onScanCallback` only while the
global callback Binder is alive. The callback arguments are name, Bluetooth address,
RSSI, four little-endian two-byte identifier strings, one one-byte identifier string,
and one final two-byte string derived directly from advertisement positions. It does
not forward the raw advertisement. Malformed/null data and callback exceptions can be
suppressed by the containing exception path; duplicates are not deduplicated.

The same result handler has two automatic branches. OTA state can stop scanning and
start a file transfer when the derived name equals either the selected address with
separators removed or the selected name. Reconnect state can stop scanning and connect
when the result address equals the remembered target. Scan discovery therefore has
side effects beyond reporting devices.

Three app-owned OTA activities separately use one legacy `startLeScan` and one
`stopLeScan` call each. They apply no UUID filter and post result handling to the UI
thread. Their parsed-advertisement UUID loop does not use the UUID value: a result with
no parsed UUID is skipped, while multiple UUIDs repeat the same target comparison.
Firmware OTA compares the derived address-as-name and, in one mode, the remembered
name; dial and wallpaper transfer compare the raw address. A match retains the device,
stops scanning, and launches the transfer action. Each scan stops after ten seconds;
dial and wallpaper emit their own failure projection, while firmware OTA does not.
The main embedded-SDK executable start/stop path uses the modern scanner; its legacy
callback object is present but no corresponding SDK start/stop invocation is observed.

## Connection, discovery, and notification ordering

Four logical `connectGatt` flows are present: ordinary manual, ordinary reconnect,
embedded-SDK SUOTA, and app-owned OTA. Each branches between the pre-API-23 overload
and the API-23+ LE-transport overload, yielding eight call expressions. Manual connect
rejects while shared SDK state is nonzero and re-emits that SDK state; Android GATT
duplicate state callbacks are separately suppressed. It records name/address before
adapter/address validation, closes retained GATTs, uses `autoConnect=false`, and can
retain a null returned GATT while reporting connecting/success. Reconnect requires the
remembered address and uses `autoConnect=true`.

`connectBt` clears user-disconnect and the last Android state, persists/starts only at
shared status 200, and returns that status rather than acceptance. `disconnectBt(true)`
clears in-memory name/address and persisted address but not persisted name;
`disconnectBt(false)` retains the target. `closeConnection` clears target/address,
marks user-disconnected, and closes/nulls current GATT. `getConnectedDevice` returns
the remembered address. `isConnectBt` is false only in SDK states 0 or 1.

Android status 257 disables the adapter and schedules re-enable after two seconds.
Connected requests high priority with ignored return, resets retry state, and starts
discovery. Disconnected reflectively refreshes the callback GATT, cancels timers, then
closes for a user disconnect or reconnects after five seconds. Status 8 or 19 clears
readiness and forces reconnect-needed.

Static ordering is:

1. manual connect reads a shared SDK status without awaiting any pending validation;
2. the target is persisted and Android GATT connect starts;
3. Android link connection precedes vendor-route readiness;
4. service discovery permits up to three attempts, with a 30-second timer each;
5. service acceptance clears the command queue before required endpoint validation;
6. primary characteristic initialization waits 500 ms;
7. notification enable and descriptor-write submission returning true is treated as
   dispatch acceptance;
8. source connected state is reported before descriptor callback and device policy;
9. one special descriptor status disconnects/refreshes cache, while every other status,
   including other failures, continues; and
10. every non-special result queues an implicit device-time write.

This ordering specifies recovered source behavior, not a safe or successful protocol.

`discoverServices()` return is ignored. Discovery flattens all characteristics and
caches services by MAIN TX, raw TX, and each dynamic write UUID. Readiness requires
only MAIN RX and MAIN TX, not raw endpoints. Characteristic lookup is UUID-only,
case-insensitive, and takes the first flattened match across services. Successful MAIN
readiness clears retry/reconnect state and user-disconnect; a missing pair schedules
reconnect. Primary initialization enables MAIN RX and configured dynamic-notification
UUIDs; raw notification remains separately caller-controlled.

## Dynamic GATT and callback behavior

`setUuid`, `writeCharacteristic`, `openRawDataNotification`,
`onCharacteristicChanged`, and `onCharacteristicWrite` are distinct functions.

- `setUuid` retains caller notification/write arrays by reference without validation or
  copying. Notification identifiers are enabled after discovery. Write identifiers are
  used as both service-cache keys and characteristic UUIDs. Its boolean suppresses
  local MAIN/raw broadcasts, but not generic characteristic callbacks.
- `writeCharacteristic` accepts caller-selected identifier and bytes and bypasses the
  fixed MAIN/raw packet taxonomy. It returns `0` for no GATT, `1` for no cached
  service, `2` for no characteristic, and `3` for an exception. Otherwise it ignores
  Android's write return and returns the shared authorization status.
- `openRawDataNotification` controls raw notification/descriptor submission; its
  enable path requests MTU 247, waits two seconds regardless of the MTU callback, then
  enables raw RX. Its callback indicates local descriptor-submission acceptance, not
  descriptor completion. Disable uses the shared release helper described below.
- `onCharacteristicChanged` forwards identifier/current value through parsing/logging
  and route selection. It copies the current value, emits a route-local broadcast
  unless suppressed, and independently invokes the generic callback. A null value can
  fail before protected callback delivery.
- `onCharacteristicWrite` forwards identifier/current value/status but also releases a
  global completion latch without checking status.

Notification setup has a recovered APK bug: the return from
`setCharacteristicNotification` is logged but ignored, and the CCCD value is always
ENABLE even for a disable request. Release can therefore disable local notification
while writing remote enable. A missing CCCD returns false; descriptor submission false
schedules disconnect after 100 ms. The raw-enable callback is emitted only for raw RX,
enable=true, and accepted submission. Descriptor status 257 disconnects; every other
status, including other failures, triggers device-time synchronization only for MAIN
RX. Raw and dynamic descriptor completions have no projection.

Connection priority `1` is requested after link connection and its return is ignored.
RSSI submission is ignored and its callback discards Android status. The ordinary read
callback only logs identifier/status. MTU callback success/failure is only logged.
All callbacks operate on shared current-GATT/session state rather than a connection
generation.

## Classic Bluetooth, bonding, RFCOMM, and HID

Android bonding, classic discovery, classic profile proxy state, vendor binding, GATT
readiness, and HID service presence are independent. Classic info/name callbacks on
MAIN opcode `45` do not prove profile attachment or OS bond state. RFCOMM evidence is
limited to socket construction and close; actual reviewed OTA transfer uses GATT.

Classic-information handling can initiate OS bonding. After bond completion, hidden
profile helpers attempt Headset and A2DP connection and priority changes with retry and
discovery behavior. No raw Classic audio stream is implemented in reviewed owned code.

There is no direct owned-scope Android HID-device-role reference. Standard HID service
or report metadata on a physical ring is a separate standards/device observation and
cannot be inferred from APK API references. No owned HID-host, general input-injection,
AccessibilityService, keyboard, mouse, or gesture-dispatch path is present.

## SUOTA roles under `fef5`

| Role | Characteristic | Required | Static access role |
|---|---|---:|---|
| memory device | `8082caa8` | yes | control write |
| GPIO map | `724249f0` | yes | control write |
| memory info | `6c53db25` | yes | status read |
| patch length | `9d84b9a3` | yes | control write |
| patch data | `457871e8` | yes | chunk write |
| status | `5f78df94` | yes | notification |
| version | `64b4e8b5` | no | metadata read |
| patch-data size | `42c3dfdd` | no | metadata read |
| MTU | `b7de1eea` | no | metadata read |
| L2CAP PSM | `61c8849c` | no | metadata read |

The recovered flow includes file materialization, XOR append, control writes,
write-without-response chunks, status/write callbacks, finalization, and
disconnect/reboot-shaped behavior. It does not yet establish authenticated eligibility,
file/read bounds, memory/GPIO values, chunk acceptance, cursor/retry correctness,
finalize/reboot acknowledgement, status meanings, success terminal, or model/firmware
support.

## Runtime and hardware matrix required

For each ring model and firmware, a later hardware profile needs observed services,
characteristics, descriptors, properties, instances, MTU, connection priority, scan
identity, pairing/bond requirements, notification activation result, reconnect
behavior, request direction, callback timing/multiplicity, and firmware status meaning.
The APK can specify phone-side behavior, but it cannot alone prove these
peripheral-owned facts.
