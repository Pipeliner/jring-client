# Clean-room APK data, cloud, and Android integration specification

Status: bounded static domain inventory. The 35 permissions, nine features, and 15
SQLite tables are closed populations; preference keys, files, outbound call sites,
phone-integration edges, retention, and rendered consumers are grouped domains rather
than exhaustive row populations. Server and Android/device runtime results remain
unknown.

## Declared Android authority

The manifest's 35 permission declarations partition as follows:

| Permission purpose | Count | Included authority |
|---|---:|---|
| Bluetooth / nearby devices | 4 | legacy Bluetooth/admin and modern scan/connect |
| calls and contacts | 4 | call log, contacts, phone state, answer calls |
| camera, storage, and media | 7 | camera, legacy read/write storage, modern image/audio/video reads, media-content control |
| location | 3 | coarse, fine, and background location |
| network state | 3 | Wi-Fi state, network state, network-state change |
| service, notification, power, and network execution | 8 | Internet, foreground services, connected-device foreground service, battery-optimization request, wake lock, keyguard disable, notification posting, vibration |
| flashlight | 1 | legacy flashlight permission |
| advertising services | 4 | attribution, ad ID, custom audience, and topics |
| install attribution | 1 | Play install-referrer binding |
| total | 35 | exact manifest denominator |

The nine feature nodes declare camera, autofocus, microphone, required BLE, required
OpenGL ES 2.0, and optional network location, GPS, telephony, and Wi-Fi. A declaration
is authority/compatibility metadata, not proof that the app exercises it correctly.

The exact Android permission names are:

`VIBRATE`, `BLUETOOTH`, `BLUETOOTH_SCAN` (`neverForLocation`),
`BLUETOOTH_CONNECT`, `BLUETOOTH_ADMIN`, `READ_CALL_LOG`, `READ_CONTACTS`,
`READ_PHONE_STATE`, `ANSWER_PHONE_CALLS`, `CAMERA`, `ACCESS_COARSE_LOCATION`,
`ACCESS_FINE_LOCATION`, `ACCESS_WIFI_STATE`, `ACCESS_BACKGROUND_LOCATION`,
`ACCESS_NETWORK_STATE`, `WRITE_EXTERNAL_STORAGE`, `INTERNET`,
`CHANGE_NETWORK_STATE`, `FOREGROUND_SERVICE`,
`FOREGROUND_SERVICE_CONNECTED_DEVICE`, `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`,
`WAKE_LOCK`, `DISABLE_KEYGUARD`, `POST_NOTIFICATIONS`, `READ_MEDIA_IMAGES`,
`READ_MEDIA_AUDIO`, `READ_MEDIA_VIDEO`, `READ_EXTERNAL_STORAGE`,
`MEDIA_CONTENT_CONTROL`, `FLASHLIGHT`, `ACCESS_ADSERVICES_ATTRIBUTION`,
`ACCESS_ADSERVICES_AD_ID`, `ACCESS_ADSERVICES_CUSTOM_AUDIENCE`,
`ACCESS_ADSERVICES_TOPICS`, and the Play install-referrer binding permission.

The exact named feature nodes are `android.hardware.camera`,
`android.hardware.camera.autofocus`, `android.hardware.microphone`, required
`android.hardware.bluetooth_le`, optional `android.hardware.location.network`,
optional `android.hardware.location.gps`, optional `android.hardware.telephony`, and
optional `android.hardware.wifi`; the ninth is required OpenGL ES 2.0 expressed by
`glEsVersion` rather than a feature name.

## SQLite storage — 15/15 tables

| Table/domain | Stored functions |
|---|---|
| generic running data | string key/value application state |
| device information | remembered ring identity, version, binding, and display fields |
| sport history | time-series step, distance, calories, activity type, heart rate, account/device IDs, and cloud/Google-Fit sync state |
| alarms | ordinary, sedentary, drink, medicine, custom, quiet, sleep, and automatic-heart schedules |
| run record | run summary, pace, distance, calories, steps, time, heart-rate summary, type, and completion |
| run history | timestamped phone location, altitude, accuracy/radius, direction, satellite count, speed, source type, and later heart rate |
| health history | typed local measurement values and upload state |
| ECG record (legacy) | report summary, scores, positions, suggestions, and identity/time fields |
| ECG history (legacy) | ECG/heart/blood sample text |
| ECG record v2 | session/report summaries, blood pressure, heart-rate statistics, event counts/labels, score, suggestion, and identity/time fields |
| ECG sample history v2 | raw/processed/base-filter samples and sync state |
| ECG session v2 | session bounds, sample count, event counts, type, and sync state |
| contacts | ring contact ID, name, phone number, and update time |
| cards | ring card ID, name, content, and update time |
| canned message responses | ring response ID, content, and update time |

Database upgrades add Google-Fit sync markers, device version/policy fields, run heart
statistics, and run step-presence state. The helper supports create, query, update, and
delete operations for these domains and a local log writer. No database encryption or
field-level protection is visible in the reviewed app-owned helper.

## Other local persistence and files

Preferences/key-value state covers account/session identifiers, privacy acceptance,
body/profile values, device identity and binding, feature flags, selected notification
applications, reminder configuration, sync cursors, latest measurements, weather and
location state, firmware/dial metadata, custom-wallpaper geometry, Google-Fit state,
and caches.

The app-owned running-state helper has at least 318 read and 246 write call sites,
separate from direct preference access; these are call-site counts, not unique-key
counts. Twelve database upgrade steps add the fitness-sync, device-policy, run-heart,
and step-presence fields summarized above. Two provider-path resources configure four
roots: two external-cache roots, one broad external-storage root, and one internal-files
root. All six installed providers are dependency-owned.

App and shared/external files cover firmware, dial packages and previews, generated
wallpaper binaries/images, avatar and temporary images, ECG share images, camera/QR
media, downloaded manuals/content, feedback attachments, and SDK/application logs.
The BLE service unconditionally calls the SDK logging toggle with `enabled=true` when
binding to the SDK; this is not a user opt-in. App-owned logging also writes selected
notification sender/content and run coordinates. The manifest retains legacy external-storage modes alongside modern media
permissions and file providers.

Static review does not establish a unified retention schedule, secure deletion,
database encryption, log redaction, backup exclusion, or successful cleanup for every
failure branch. `allowBackup` is enabled. Logs can contain identifiers, GATT payloads,
credentials, notification data, coordinates, and profile/environment state.

## Outbound network and account purposes

| Purpose | Static behavior | Security/terminal boundary |
|---|---|---|
| first-party account | register, login, password recovery/change, profile update, logout/account deletion state | custom HTTP/JSON flows; local token/member state; server retention/result not independently known |
| device policy / gear service | SDK validation, ring/product policy, and selected binding-related cloud requests | cloud authorization is distinct from device binding and OS bond |
| sport/location backend | upload or synchronize selected activity/run/location data | phone location and account/device identifiers may be transmitted |
| firmware update | fetch update metadata and binaries | cleartext unauthenticated metadata and weak digest; detailed in the OTA spec |
| dial catalog/content | fetch/cache catalog JSON, preview images, and selected transfer file | metadata/file integrity and transfer terminal are separate |
| weather | fetch current, forecast, air-quality, and special-city data from remote services | location/city and environment leave the phone; results are cached and sent to the ring |
| feedback | upload selected images to object storage, then submit feedback and attachment references | APK embeds long-lived upload-signing material and logs a generated upload token |
| WeChat sport | submit a vendor-service request used by the integration flow | cleartext vendor request observed; third-party success remains external |
| Google Fit | request Google account/fitness authority and insert or update local sport-history datasets | Google service state is independent of ring sync and vendor-cloud sync |
| app/manual content | check app update metadata and open/download configured help/manual content | cleartext download surfaces exist |

The app permits an offline/skip-login main flow. Account-cloud functionality is
therefore an optional app workflow, not a prerequisite implied by the ring protocol.
Several first-party, weather, firmware, dial, manual, and sport requests use cleartext
HTTP because the manifest explicitly permits cleartext traffic. No committed clean-room
spec reproduces embedded credentials, tokens, hostnames, artifact hashes, or private
configuration values.

The sanitized Java URL-literal population is 43 occurrences, 20 unique literals, and
nine host groups. After excluding three Android-namespace literals and two unreferenced
SDK constants, 38 operational-or-referenced occurrences remain: 30 cleartext across 14
unique literals and eight TLS across four. Their purpose partition is first-party
account/profile/feedback 14; weather/air-quality six; SDK validation four; firmware or
app-update three with one SDK/application overlap; route/location two; third-party sport
two; feedback upload/assets two; device policy two; and one each for dial catalog,
remote manual, and external sharing. Resource URLs are a separate population: 28 XML
occurrences across five values and ten legal-HTML occurrences across five external
targets. Resource strings are not promoted to runtime network calls without activation
evidence.

## Phone integrations

| Phone surface | APK function |
|---|---|
| notification listener | read title/text/package, briefly deduplicate, filter enabled packages/content, forward eligible text/app identifiers, log sender/content, restart on destruction, and start the BLE service |
| calls and contacts | read contact/call/phone state, forward incoming-call state/identity, answer or control calls where allowed, and synchronize selected contacts |
| media and volume | observe host volume, forward volume state, receive ring media/volume actions, and interact with media control |
| camera | open/close/capture through the app camera in response to local UI or device action |
| short-video remote | configure and handle remote-action mode separately from normal media control |
| location | capture run points through the manifest location-typed service and refresh weather based on distance/time policy; no owned foreground promotion is observed in that service |
| images and sharing | crop/compose wallpapers, create ECG/activity share images, share through Android/Facebook/Twitter surfaces, and store through MediaStore/file providers |
| QR | scan a QR payload and parse query parameters used in device-selection/setup paths |
| classic Bluetooth | inspect profile state, initiate bonding/profile helpers, and keep this state separate from BLE readiness and vendor binding |

### Proprietary remote device actions

The ring's MAIN device-action callback drives an app-owned action switch with these
phone-side effects: play a maximum-volume find-phone sound and schedule volume reset;
open, close, or trigger the app camera; answer or end a call; conditionally refresh
phone location/weather; play/pause, next, or previous media; synchronize time; and
raise or lower host media volume. These are vendor-BLE remote-control actions, not
Android HID reports.

The SDK also decodes G-sensor, touch, raw-AI, command, and audio callback families, but
the app's corresponding callback overrides are empty. Phone accelerometer and
magnetometer use is limited to camera orientation. Ring step data contributes to run
recording. No app-owned Android HID-device role, `InputManager` injection,
AccessibilityService, keyboard, mouse, or general desktop-input path is present.

Direct SMS-helper methods have zero owned call sites and the manifest does not declare
`SEND_SMS`. The inbound ring SMS-response callback only logs in this build. Contact,
call-state, and canned-response synchronization must therefore not be described as
proof of active phone SMS sending.

### Phone Wi-Fi and WebView behavior

On the connected device-AP branch the SDK can add/suggest, enable, and reconnect a
phone Wi-Fi network whose SSID is derived from persisted device identity, using an
embedded credential. It then projects the derived host address or starts the separate
phone-managed FTP path. This mutates phone network configuration and is distinct from
ring GATT transport.

One owned content screen enables JavaScript and WebView debugging. Legal pages load
local content; the manual loads a cleartext remote URL containing a device-derived
prefix and locale. In-view navigation is unrestricted in reviewed owned code. No
JavaScript bridge or custom SSL-error override is observed. These are APK behaviors,
not requirements to embed a browser in the later Linux client.

## Background and lifecycle work

The application class requests manifest persistence, initializes SDK/dependency state, and tracks activity
lifecycle. The BLE service runs in a separate named process and foreground-service
mode, persists selected target/configuration, translates SDK callbacks to local
broadcasts, schedules sync/retry/timeout work, and posts a main-activity notification.
The location service owns run-recording location work. The notification-listener service
may start/rebind the BLE service and forward events.

No app-owned JobScheduler or WorkManager path is observed. One repeating AlarmManager
schedule targets run recording, but its matching receiver is process-local while the
PendingIntent sends a system broadcast; no manifest/system receiver closes that route,
so delivery is unestablished. The location service stores points in SQLite and text
logs but does not promote itself to foreground. An additional notification-listener
implementation and an undeclared receiver exist in owned code without a proven entry
path.

Advertising/attribution permissions and bundled dependencies do not prove an owned
analytics or crash-emission call. App code manually initializes its social SDK while
manifest automatic initialization is disabled; sharing is established, while any
automatic telemetry caused by that initialization remains unknown.

The package has no app-owned static receiver, boot receiver, or companion-device
service. It nevertheless registers dynamic local and system-context receivers at
runtime. Sender trust, export state, registration ownership, and unregister symmetry
are specified in [APK_PLATFORM_SPEC.md](APK_PLATFORM_SPEC.md).

## Client reconstruction boundary

This specification records what the Android APK does. A Linux ring client can reproduce
ring-facing jobs without recreating vendor accounts, advertising SDKs, social sharing,
phone call control, Android providers, or unsafe cloud/firmware behavior. That product
scope decision belongs to the later client SDD; it must not erase these APK behaviors
from the clean-room source specification.
