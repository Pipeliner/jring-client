# Clean-room APK Android and non-wire functionality specification

Status: exact SDK-interface platform surfaces plus reconciled package-level inventory.
Whole-app functional roles are specified in the UI and data/platform appendices.

## Local BLE and dynamic-GATT request behavior — 14

| Operation | Recovered local/platform behavior | Bluetooth effect | Important boundary |
|---|---|---|---|
| `closeConnection` | set user-disconnected, clear in-memory target, release notification state, reset connection state; persisted address clears but name does not | close GATT object | teardown ordering and stale callbacks require full instruction review |
| `connectBt` | clear user-disconnected/state; on shared status 200 store/persist name/address and start reconnect flow | GATT connect/reconnect | validation status is neither device policy nor owner authorization |
| `disconnectBt` | set user-disconnect policy, conditionally clear target, release notification state | GATT disconnect | false retains target; true clears persisted address but not name |
| `getConnectedDevice` | return remembered address field | local query only | does not query Android radio/link |
| `getDeviceRssi` | schedule remote RSSI callback | Android remote-RSSI read | immediate return is not RSSI; callback discards Android status |
| `isAuthrize` | return current shared SDK-validation status | local query only | does not contact network, return device policy, or prove ownership |
| `isConnectBt` | read broad SDK connection state | local query only | true does not prove link, discovery, endpoints, notifications, policy, or ownership |
| `openSDKLog` | toggle file logging and choose runtime subdirectory/filename; app BLE-service binding calls it with enabled=true unconditionally | none directly | logs can include identifiers, GATT payloads, credentials, notifications, coordinates, and profile/environment values; path validation incomplete |
| `scanDevice` | one boolean starts/stops SDK scan timers and retry counter if shared status is 200 | active scan toggle | start/stop ownership, permission/API behavior, and timeout require call-site spec |
| `setOption` | cache user/device profile, alarms, and weather for later commands if shared status is 200 | none directly | retains body/schedule/alarm/environment state |
| `setScanMode` | set future Android scan settings code | scan configuration | code is not validated; operation does not start scan |
| `setUuid` | store dynamic UUID arrays and raw-broadcast suppression policy for later notification/write lookup | dynamic GATT configuration | arrays are not validated/copied; operation itself does not subscribe/write |
| `unregisterCallback` | clear one global callback slot | none directly | callback argument identity is ignored; one caller can clear another’s slot |
| `writeCharacteristic` | dynamic service/characteristic lookup, set value, invoke Android write, report through global callback | arbitrary GATT write | bypasses vendor queue and validation gate; missing service/false write return semantics are unsafe/ambiguous |

These rows specify recovered APK behavior only. They do not authorize or prescribe a
client implementation.

## Non-Bluetooth platform request behavior — 10

| Operation | Behavior class | Side effects / distinction |
|---|---|---|
| `getDialServerInfo` | cache then vendor network | device/dial request and Android cache/network behavior |
| `registerCallback` | callback registration plus SDK validation | installs shared callback; bundled SDK configuration; fresh cache or vendor validation |
| `registerCallback2` | callback registration plus SDK validation | same shared slot; caller-provided configuration rather than bundled configuration |
| `startFtpDownloadTask` | phone-managed FTP | phone network plus filesystem path/result behavior |
| `saveFileToSystemAlbum` | Android MediaStore/broadcast | local file/media write plus broadcast |
| `translateBmpToBin` | local bitmap conversion | source/destination/image configuration and filesystem conversion |
| `connectFtp` | constant no-op stub | no named connection in this SDK build |
| `getDeviceFileState` | constant no-op stub | response parsing exists elsewhere but this request is inert |
| `getWifiState` | constant no-op stub | Wi-Fi callbacks exist elsewhere but this request is inert |
| `setDeviceFileState` | constant no-op stub | no named mutation in this SDK build |

Interface rows do not form a whole-app cloud/filesystem/database/media denominator.

MediaStore audio/video rows are inserted with `is_pending=0` before copying in 1 KiB
chunks. Insert/input/output/copy failure returns null without deleting an already
inserted row, so a visible empty or partial row can remain. Video inserts before
checking a null source. The audio timestamp argument is unused; video stores the
supplied value as capture time and its seconds form as added time.

## Manifest population

| Surface | Count / fact |
|---|---|
| APKs | 20: base + 17 locale + 1 density + 1 arm64 |
| DEX units | 3; one with recognized owned app/SDK scope, two classified without it |
| permissions | 35 |
| features | 9 |
| activities | 79 |
| services | 6 |
| receivers | 2 |
| provider components | 6 |
| provider query nodes | 2; package-visibility declarations, not components |
| app-owned services | 3, all non-exported |
| BLE foreground service | 1 |
| app-owned exported activities | 2, including one Bluetooth-controller activity |
| non-exported OTA activities | 3 |
| app-owned static receivers | 0 |
| static Android Bluetooth actions | 0 |
| boot receiver / companion-device service | absent |
| BLE hardware feature | required |
| Bluetooth permissions | two legacy; modern scan/connect present; advertise absent |
| connected-device foreground-service permission | present |

The decoded manifest is not independently corroborated. Permission and feature
identities and component ownership/export partitions are published in the UI/data
appendices. Their complete runtime-permission/API-level call-site map remains unknown.

## Dynamic receivers

Twenty-five registration files include 17 Bluetooth-filter files: 16 process-local and
one system-context. The primary filter contains seven unique Android Bluetooth actions,
one duplicate registration, four handled actions, and three registered actions without
an observed receiver case. The system receiver contains 12 actions, including two
BLE-related app actions; it is exported on the current API, has no observed sender
permission, and has no matching unregister in the same registration domain.

No bridge from the 16 process-local filters to Android system broadcasts was observed.
Delivery, sender trust, lifecycle ownership, and teardown behavior remain unverified.

## Reflection and activation

Five owned files (two application, three SDK) contain ten reflective methods and 11
invokes. The observed targets are constant Android helpers:

| Category | Methods / invokes |
|---|---:|
| bond hidden API | 3 / 3 |
| telephony hidden API | 1 / 2 |
| classic-profile hidden API | 3 / 3 |
| GATT cache refresh | 3 / 3 |

No bounded reflection row activates standalone dial transfer. Nine constant targets
and 11 invokes are different metrics. Review is bounded to the five observed files and
does not exclude runtime-generated, encrypted, external, or dependency activation.

The dial-focused activation trace contains 19 Binder stubs, 13 proxies, 25 transact
files, 23 `onTransact` methods, nine relevant request transactions, seven relevant
callback transactions, and zero application outbound invokes on that interface. Six
application explicit launch sites and 11 relevant resource XML files contain no
standalone dial launch/navigation edge. Generic OTA construction and a direct owned
service bind are observed; standalone dial construction/bind/activation remains
inconclusive rather than proven dormant.

## Resources

The base contains 1,107 decoded XML files. Keyword scanning finds 24 matching XML files
and 733 matching named entries; these entries are not capabilities. Resource payload
and locale semantic review are incomplete. One SDK configuration asset contains
credential-bearing configuration, but its material is not part of the clean-room
specification.

Resource work still requires a complete ownership/type partition and activation map
for layouts, navigation, menus, deep links, preferences, services, jobs, receivers,
permissions, localized strings, WebView/assets, and feature configuration.

## Native surface

One arm64 library has two owned load sites. Static accounting finds ten native
declarations: three application, six embedded SDK, and one dependency. Three JNI
exports are all matched to the application declarations; their three rooted entries
and 30 indirect calls classify as image/wallpaper processing. There are 43 named
undefined imports, four needed libraries, and two runtime initializers.

No rooted Bluetooth, dial, reflection, dynamic-JNI-registration, or module-load edge
was observed. Seven declarations remain unresolved, including all six SDK declarations.
Whole-library instruction review and possible external/runtime SDK binding remain
incomplete; zero Bluetooth/GATT/HID/dial symbol matches does not prove native absence.

## UI and whole-app behavior

The 79 activities refine to 65 app-owned functions and 14 bundled-dependency surfaces;
the 11 concrete fragment classes (ten statically activated and one activation-unknown),
three app-owned services, application class, and dependency
component roles are accounted in [APK_UI_SPEC.md](APK_UI_SPEC.md). Fifteen SQLite
tables, preference/file domains, outbound-service purposes, all 35 permissions, all
nine feature nodes, phone integrations, and background roles are accounted in
[APK_DATA_PLATFORM_SPEC.md](APK_DATA_PLATFORM_SPEC.md).

These appendices establish a bounded static domain partition and complete closed-count
populations only where explicitly stated. They do not promote
runtime rendering, accessibility quality, permission behavior, server responses,
retention outside the APK, or per-device behavior to known facts.
