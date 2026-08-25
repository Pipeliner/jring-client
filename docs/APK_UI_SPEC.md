# Clean-room APK user-interface and component specification

Status: complete manifest-component and named-class partition, with a bounded static
function/action inventory. Runtime reachability/rendering, unenumerated listener paths,
server availability, peripheral support, and user-success outcomes remain unknown.

## Component denominator

| Manifest surface | Total nodes | App-owned | Bundled dependency | Important distinction |
|---|---:|---:|---:|---|
| activities | 79 | 65 | 14 | two app-owned activities are exported |
| services | 6 | 3 | 3 | all app-owned services are non-exported |
| receiver components | 2 | 0 | 2 | both are Facebook SDK receivers |
| provider components | 6 | 0 | 6 | two additional `<queries><provider>` nodes are package-visibility declarations, not components |
| application class | 1 | 1 | 0 | owns process initialization and activity tracking |

The earlier aggregate of eight provider XML nodes is therefore refined to six actual
application provider components plus two provider queries.

Three activities are exported: app-owned `SplashActivity` and `DupMainActivity`, plus
the dependency `CustomTabActivity`. `SplashActivity` is the only app activity with an
intent filter (MAIN, VIEW, and LAUNCHER), and that filter has no `<data>` element. There
is no app-owned manifest deep link and there are zero activity-alias nodes. All app
services are non-exported; the only exported
service is a Google dependency service. The only exported provider is the Facebook
content provider.

The package also contains 11 concrete app fragment classes: four reachable main-pager
tabs, six initial profile-wizard pages, and one data fragment whose activation is not
statically established. `BaseFragment` and `GuideFragment` are framework/base classes,
not additional concrete pages.

## App-owned activities — 65/65

Every manifest activity is assigned exactly once below. Names identify clean-room
functional surfaces; they do not prescribe a Python UI.

### Startup, account, profile, legal, and support — 10

| Activity | Static function |
|---|---|
| `SplashActivity` | choose signed-in main flow or sign-in flow after a delay |
| `LoginActivity` | first-party credential login; links to registration, password recovery, agreement, and privacy content |
| `RegisterActivity` | first-party account registration plus agreement/privacy links |
| `ForgetPwdActivity` | request and apply password recovery |
| `GuideActivity` | host the initial gender, height, weight, birth date, unit, and goal wizard |
| `UserInfoActivity` | view/edit account and body/device profile, avatar, logout, account deletion, and password navigation |
| `ChangePasswordActivity` | submit an authenticated password change |
| `DupAboutActivity` | app/version/about surface |
| `HtmlContentActivity` | render local agreement/privacy content or configured manual/help content |
| `FeedbackActivity` | compose feedback, attach/upload an image, and submit it to the vendor service |

Account state, identifiers, profile fields, and session token are persisted locally.
The account functions are vendor-cloud behavior and are not required to reproduce the
ring protocol itself.

### Shell, connection, and broad settings — 3

| Activity | Static function |
|---|---|
| `DupMainActivity` | exported single-task application shell; binds the BLE service, hosts four pager tabs, coordinates permissions, sync, device state, phone integrations, classic Bluetooth, and OTA prompts |
| `SearchDeviceActivity` | explicit scan/discovery and device selection surface |
| `SettingMoreActivity` | additional settings hub for quiet/sleep/heart monitoring, firmware update, sport integration, and related switches |

### Dashboard details and history — 10

`DetailActivity` is a shared detail base. `DetailWalkActivity`,
`DetailSleepActivity`, `DetailHeartActivity`, `DetailBloodActivity`,
`DetailBloodSugarActivity`, `DetailOxygenActivity`,
`DetailBodyTemperatureActivity`, `DetailPressureActivity`, and
`DetailSportActivity` display the corresponding local/current/history series and
charts. Their data sources include ring callbacks, SQLite history, and cached summary
state; a visible chart is not proof of sensor accuracy or medical suitability.

### ECG — 9

| Activity | Static function |
|---|---|
| `EcgHealthActivity` | ECG hub: guide, measurement, session history, and heart-history navigation |
| `EcgGuideActivity` | measurement guidance |
| `EcgTestActivity` | live ECG measurement/session capture |
| `EcgXtTestActivity` | alternate ECG measurement path and history navigation |
| `EcgHistoryActivity` | recorded ECG list and report navigation |
| `EcgSessionHistoryActivity` | session list with report/raw-history navigation |
| `EcgHistoryHeartActivity` | heart-event/history presentation |
| `EcgReportActivity` | stored ECG report/score/suggestion presentation |
| `EcgShareActivity` | render/share an ECG result image |

ECG sessions, samples, derived event counts, scores, suggestions, heart rate, and blood
pressure fields are stored in dedicated local tables. These are app/device outputs,
not validated diagnoses.

### Device configuration, notifications, and content — 18

| Activity | Static function |
|---|---|
| `DialMarketActivity` | fetch/cache a dial catalog, select an item, and hand it to dial transfer |
| `CustomWallpaperActivity` | choose/crop/compose an image and hand the generated wallpaper to transfer |
| `NotifyActivity` | enable call/SMS and named application-notification forwarding |
| `ContactActivity` | maintain ring contact records and trigger contact synchronization |
| `EditlistActivity` | reorder/edit a local list used by device content flows |
| `AlarmClockActivity` | list device alarms and open alarm editing |
| `AlarmClockInfoActivity` | edit a standard alarm |
| `AlarmSedentaryInfoActivity` | configure sedentary reminders |
| `AlarmDrinkActivity` | configure drink reminders |
| `AlarmPillActivity` | configure medication reminders |
| `AlarmCustomActivity` | configure a custom reminder |
| `QuiteModeActivity` | configure quiet/do-not-disturb timing |
| `SleepActivity` | configure sleep timing |
| `HeartrateTestActivity` | configure automatic heart-rate monitoring |
| `BpAdjustActivity` | enter and synchronize blood-pressure calibration values |
| `ECardSimpleActivity` | maintain simple card text/content and synchronize it |
| `SmsRspSimpleActivity` | maintain canned message responses and synchronize them |
| `ShortVideoActivity` | configure the short-video/remote-control feature |

### Sport, location, and external fitness integrations — 6

| Activity | Static function |
|---|---|
| `SportHintActivity` | pre-run instructions and start handoff |
| `RunRecordActivity` | live phone-assisted run recording using the location service |
| `RunHistoryActivity` | list stored runs |
| `RunDetailActivity` | map and summary for one stored run |
| `WechatSportActivity` | WeChat-sport integration guidance/configuration |
| `GoogleFitActivity` | Google account authorization and local sport-history upload state |

### Female-cycle and pregnancy reminders — 4

`FemaleReminderActivity` selects and configures the cycle, pregnancy, or parent mode;
`FemaleReminderCalendarActivity` presents the calculated calendar;
`MenstruationSetActivity` edits start date, period, and duration; and
`PregnancySetActivity` edits due date and child-related state. Configuration is stored
locally and selected reminder fields are sent to the ring.

### Camera and QR — 2

`CameraActivity` supplies an app camera/capture surface used by remote-camera and image
flows. `DecoderActivity` scans QR codes. Camera control, image storage, and the ring's
camera-action callback are separate behaviors.

### Firmware and content transfer — 3

`OtaActivity` presents firmware update state; `OtaDialActivity` presents dial transfer;
and `OtaWallpaperActivity` presents wallpaper transfer. Firmware SUOTA, dial transfer,
and wallpaper transfer are distinct engines and terminal contracts. See
[APK_OTA_SPEC.md](APK_OTA_SPEC.md).

The category count is 10 + 3 + 10 + 9 + 18 + 6 + 4 + 2 + 3 = 65.

## Main-pager fragments — 4, plus one unresolved concrete fragment

| Fragment | Static function |
|---|---|
| `FragmentMain` | current health/activity dashboard, live measurement controls, history/detail navigation, and history synchronization |
| `FragmentSport` | phone-assisted sport start and run-history access |
| `FragmentPerson` | profile, female reminder, Google Fit, feedback, about, manual, privacy, and agreement navigation |
| `FragmentSetting` | device/content/notification/alarm/reminder/camera/card/message/OTA and connection settings |

`MainPagerAdapter` has an item count of four and references only the four rows above.
`FragmentData` contains an aggregate data/history presentation and layout, but it has
zero external owned-source references, no explicit construction edge, no pager entry,
and no resource `<fragment>` activation. It remains the eleventh concrete fragment
class with static reachability `unknown`, not a fifth tab.

## Initial profile fragments — 6

`GenderFragment`, `HeightFragment`, `WeightFragment`, `BirthFragment`, `UnitFragment`,
and `GoalFragment` collect the initial body/profile and target settings. Their output is
both local account/profile state and, after a device is available, ring user/goal
configuration.

## Static navigation and user actions

Rendered owned source contains 77 unique explicit owned-activity Intent target
constructions from 22 caller files, naming 59 of the 65 app activity targets. They are
construction evidence, not proof that control flow reaches `startActivity` or produces
a successful launch. Major hubs are the
launcher/login pair, `FragmentSetting` with 20 device/content/settings targets,
`FragmentMain` with 13 health/detail targets, `FragmentPerson` with seven account and
help/integration targets, and `FragmentSport` with two sport targets. `GuideActivity`
explicitly constructs all six initial-profile fragments.

Six activities have no explicit incoming owned-source Intent edge: launcher-entered
`SplashActivity`, base `DetailActivity`, and `DecoderActivity`, `EcgHealthActivity`,
`EcgShareActivity`, and `EditlistActivity`. The last four remain activation-unknown
because implicit, dependency, reflective, and instruction-only edges are not fully
excluded. `FragmentData` is the separate fragment activation gap described above.

The exact ButterKnife subset contains 179 annotated click-handler methods in 50
classes, binding 183 resource-ID occurrences and 116 unique IDs. Their functional
partition is 51 device connection/settings, 37 alarms/schedules/calibration, 35
health/history dashboard, 26 entry/account/legal, 12 sport/location/fitness, seven
private-sync, four dial/wallpaper/firmware, four onboarding, and three ECG handlers.
The camera layout adds 11 XML `android:onClick` handlers for capture, gallery,
camera/video mode, settings, exposure/focus/flash, trash, and sharing. These exact
subsets overlap generated bindings and listener callbacks and are not added together
as a whole-action denominator.

Static direct Binder use contains 51 request targets and 130 unique caller-to-request
edges from 86 method nodes in 48 classes. Collapsing inner classes yields 26 top-level
callers: 21 activities, `FragmentMain`, `FragmentPerson`, `FragmentSetting`,
`SampleBleService`, and `SimpleAdapterAlarm`.

### Explicit owned-activity Intent constructions — 77/77

| Caller | Count | Target activities |
|---|---:|---|
| `AlarmClockActivity` | 1 | `AlarmClockInfoActivity` |
| `CustomWallpaperActivity` | 1 | `OtaWallpaperActivity` |
| `DialMarketActivity` | 1 | `OtaDialActivity` |
| `DupMainActivity` | 3 | `CameraActivity`, `GuideActivity`, `OtaActivity` |
| `EcgHealthActivity` | 4 | `EcgGuideActivity`, `EcgHistoryHeartActivity`, `EcgSessionHistoryActivity`, `EcgTestActivity` |
| `EcgHistoryActivity` | 1 | `EcgReportActivity` |
| `EcgSessionHistoryActivity` | 2 | `EcgHistoryActivity`, `EcgReportActivity` |
| `EcgXtTestActivity` | 1 | `EcgHistoryActivity` |
| `FemaleReminderActivity` | 3 | `FemaleReminderCalendarActivity`, `MenstruationSetActivity`, `PregnancySetActivity` |
| `FemaleReminderCalendarActivity` | 1 | `FemaleReminderActivity` |
| `FragmentMain` | 13 | `BpAdjustActivity`, nine concrete `Detail*Activity` targets, `EcgSessionHistoryActivity`, `EcgXtTestActivity`, `FemaleReminderCalendarActivity` |
| `FragmentPerson` | 7 | `DupAboutActivity`, `FeedbackActivity`, `FemaleReminderActivity`, `FemaleReminderCalendarActivity`, `GoogleFitActivity`, `HtmlContentActivity`, `UserInfoActivity` |
| `FragmentSetting` | 20 | `AlarmClockActivity`, four specialized alarm activities, `CameraActivity`, `ContactActivity`, `CustomWallpaperActivity`, `DialMarketActivity`, `ECardSimpleActivity`, `HeartrateTestActivity`, `NotifyActivity`, `OtaActivity`, `QuiteModeActivity`, `SearchDeviceActivity`, `SettingMoreActivity`, `ShortVideoActivity`, `SleepActivity`, `SmsRspSimpleActivity`, `WechatSportActivity` |
| `FragmentSport` | 2 | `RunHistoryActivity`, `SportHintActivity` |
| `LoginActivity` | 4 | `DupMainActivity`, `ForgetPwdActivity`, `HtmlContentActivity`, `RegisterActivity` |
| `RegisterActivity` | 1 | `HtmlContentActivity` |
| `RunHistoryActivity` | 1 | `RunDetailActivity` |
| `SampleBleService` | 1 | `DupMainActivity` |
| `SettingMoreActivity` | 5 | `HeartrateTestActivity`, `OtaActivity`, `QuiteModeActivity`, `SleepActivity`, `WechatSportActivity` |
| `SplashActivity` | 2 | `DupMainActivity`, `LoginActivity` |
| `SportHintActivity` | 1 | `RunRecordActivity` |
| `UserInfoActivity` | 2 | `ChangePasswordActivity`, `LoginActivity` |

Counts sum to 77 constructions across 22 callers and 59 unique app targets. The nine
concrete `Detail*Activity` targets in the `FragmentMain` row are the subclasses
enumerated above; their shared base is not an Intent target. These rows remain construction evidence, not proven
`startActivity` calls or successful launches.

## App-owned services — 3

| Service | Static function |
|---|---|
| `SampleBleService` | foreground service that binds to the embedded BLE SDK, translates its callbacks into application state/broadcasts, manages sync and selected phone integrations, and exposes the app-local BLE binder |
| `LocationService` | manifest location-typed service for phone run-location capture, including points and progress persistence |
| `NLService` | Android notification listener that filters selected packages/content and forwards eligible notifications to the ring through the BLE service |

`MusicControlService` is another notification-listener implementation present in owned
code but not declared as a manifest service in this build. It is code-surface evidence,
not a manifest entry point.

No owned `startForeground`, `stopForeground`, or notification-channel use is observed
in `LocationService`, despite its manifest foreground-service type. `SampleBleService`
does explicitly promote itself to a foreground service.

## Bundled activity and component functions

The 14 dependency activities are `PictureSelectorSupporterActivity`,
`PictureSelectorTransparentActivity`, `FacebookActivity`, `CustomTabMainActivity`,
`CustomTabActivity`, `PlayerActivity`, `GalleryActivity`, `SignInHubActivity`,
`GoogleApiActivity`, `CaptureActivity`, `UCropActivity`, `UCropMultipleActivity`,
`ComposerActivity`, and `OAuthActivity`. The three dependency services are
`ForegroundService`, `RevocationBoundService`, and `TweetUploadService`. The two
receivers are `CurrentAccessTokenExpirationBroadcastReceiver` and
`CurrentAuthenticationTokenChangedBroadcastReceiver`. The six providers are
`FileProvider`, `FacebookContentProvider`, `PictureFileProvider`,
`TrayContentProvider`, `FacebookInitProvider`, and `InitializationProvider`.

These are reachable dependency surfaces where invoked, not ring capabilities.

## Supporting UI class census

The owned UI support surface contains 17 adapters, 30 custom `View` subclasses, 62
generated view-binding files, two named dialog helpers, and no owned `DialogFragment`
or ViewModel class. Twenty-one other behavior files construct inline alert dialogs,
and the main activity references a bottom-sheet surface, so the two named helpers are
not a dialog denominator. Two map layouts embed `SupportMapFragment`; no Navigation
Component graph or resource `<deepLink>` is present.

The 17 adapters are `SessionListAdapter`, `MainPagerAdapter`,
`SimpleAdapterContact`, `ContactAdapter`, `SimpleExpandableListAdapterEcg`,
`SimpleAdaptarSport`, `EditListAdapter`, `SimpleAdapterAlarm`, `DateRecycleAdapter`,
`SmsRspAdapter`, `SimpleAdapterRun`, `SimpleAdaptarMain`, `ECardAdapter`,
`SingleChoiceAdapter`, `DragSortCursorAdapter`, `SimpleDragSortCursorAdapter`, and
`ResourceDragSortCursorAdapter`. The two named dialog helpers are `DialogLoading` and
`DialogPicker`. There are zero owned ViewModel classes.

## Static completeness and runtime limits

Fresh whole-XAPK decompilation produced source for every app-owned manifest component
without an owned hard “method not decompiled” stub. Sixty-two of 65 activities directly
select exactly one owned layout; `GuideActivity`, `DetailActivity`, and
`EcgXtTestActivity` are indirect/base cases. Twenty-three app-owned source files contain
161 decompiler warnings, and 21 embedded-SDK files contain 62 warning markers; these
therefore require
instruction-level corroboration before a warning-sensitive branch can be called exact.
The full package decompile also reported dependency-level errors; dependency behavior
is specified only to the app-visible role above.

The 21 SDK warning files reconcile to 62 markers: 27 bridge-only markers in 15 files
and 35 behavior-sensitive markers in six files. Instruction review resolves the MAIN
dispatcher, SUOTA manager, FTP, MediaStore helper, and digest-helper flows represented
in the callback/OTA/platform appendices; no warning-induced SDK control-flow ambiguity
remains.

The 23 warning-bearing app files reconcile to 161 markers: `Preview` 118;
`DupMainActivity` 8; `RunRecordActivity` 5; `FragmentMain` 4; `OtaActivity` 4;
`BluetoothManager` 3; `WeatherUtil` 2; `SampleBleService` 2; and one each in `CustomBarChartView`,
`DataBarChart`, `DetailOxygenActivity`, `DetailPressureActivity`,
`DetailSleepActivity`, `DetailSportActivity`, `FragmentSetting`, `GlideEngine`,
`IBraceletplusSQLiteHelper`, `NLService`, `OtaDialActivity`, `OtaWallpaperActivity`,
`RomUtil`, `SimpleAdapterAlarm`, and `SmartTooltipHelper`.

Their bounded semantic disposition is:

| File(s) | Static function and precision boundary |
|---|---|
| `BluetoothManager` | instruction-closed OTA memory-mode/GPIO preparation; hardware acceptance unknown |
| `CustomBarChartView`, `DataBarChart`, `SmartTooltipHelper` | drawing or tooltip behavior only; no BLE/network/storage capability hidden |
| `DetailOxygenActivity`, `DetailPressureActivity`, `DetailSleepActivity`, `DetailSportActivity` | local history queries and chart construction; no transport mutation |
| `DupMainActivity` | instruction-closed Classic/BLE/app/update receiver orchestration; content-URI real-path provider/null/cursor fallbacks remain unknown |
| `FragmentMain` | dashboard/history/sync dispatch, day/multiple-sport/advanced-history requests and persistence; exact receiver action ownership and history-loop/end/error ordering remain unknown; demo/chart helpers are local only |
| `FragmentSetting` | battery/device/bind/dial state and private contact/card/message CRC synchronization; exact action-to-side-effect order remains unknown and no acknowledgement is inferred |
| `GlideEngine` | compiler bridge around image-resource transformation only |
| `IBraceletplusSQLiteHelper` | projects pending Google-Fit sport rows; exact filter/order/cursor-error semantics remain unknown |
| `NLService` | retains/normalizes/deduplicates eligible notification title/text/package and emits a local event; exact fallback and duplicate-window edges remain unknown; downstream BLE forwarding is separate |
| `OtaActivity` | instruction-closed OTA event receiver; local step/UI/retry/reboot projections are not hardware success |
| `OtaDialActivity`, `OtaWallpaperActivity` | compiler bridges hand a `BluetoothGatt` object to the controller; they are not percentage progress callbacks |
| `Preview` | 118 markers belong to only three legacy-camera methods: camera configuration/preview, overlay drawing, and JPEG capture processing; exact rotation/stabilization/EXIF/write/cleanup ordering in `onPictureTaken` remains unknown and hides no BLE behavior |
| `RomUtil` | reflective OEM property lookup for compatibility classification |
| `RunRecordActivity` | instruction-closed location/test-location/step/timer receiver; updates local run UI without BLE writes |
| `SampleBleService` | call-state gating, deduplication, number preservation, contact lookup, local event, and forwarding pipeline; exact per-state send order and packet mapping remain unknown |
| `SimpleAdapterAlarm` | toggle/persist alarm, rebuild alarm/options collections, call `setAlarm`, then `setOption`; no UI rollback/acknowledgement observed |
| `WeatherUtil` | parse current/forecast fields and call the local listener; missing-field, exception, list-order, and terminal-callback behavior remain unknown |

Thus seven material warning-sensitive branch contracts remain explicitly unknown:
camera JPEG completion; the two `FragmentMain` branches; `FragmentSetting` routing;
notification fallback/deduplication; phone-call send ordering; and weather fallback/error
ordering. Two lower-impact platform/query edge contracts remain in URI resolution and
the pending-Google-Fit query. These are specified unknowns, not omitted capabilities.

The manifest-component and named UI-class populations are complete for the reviewed
APK. The 77 Intent constructions, 179 ButterKnife handlers, and 11 XML handlers are
closed subsets, not a whole-app action denominator. The other 245 app-owned files lack
recognized warning markers; that is not an instruction-level semantic review. Six
activity targets and `FragmentData` retain the activation qualifications above. This
document does not claim complete reachability or action semantics, nor correct
rendering for every account, locale, ring, firmware, API level, permission, or server.
