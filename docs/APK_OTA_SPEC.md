# Clean-room APK firmware and transfer specification

Status: complete static publication of the three `vendor_ota_evidence` workflow rows;
this is not the denominator for every Binder, dial, wallpaper, media, or FTP transfer
surface. Runtime peripheral behavior remains explicitly unknown. Nothing in this
document authorizes network, file, GATT, firmware, or reboot activity.

## Operation partition

| Operation | Main-channel prelude | Workflow phases | Callback groups | Static blockers | Dangerous side-effect classes |
|---|---|---:|---:|---:|---:|
| `getOtaInfo` | device-information query; queue tail; queue retained | 8 | 3 | 10 | 5 |
| `startFileOta` | mode request; queue tail after clearing the ordinary queue | 10 | 3 | 19 | 7 |
| `notifyDownloadFtpFileCompleted` | media-FTP terminal signal; queue tail; queue retained | 1 | 1 | 1 | 1 |
| total | three distinct fixed MAIN frames | 19 | 7 | 30 | 13 |

The first two operations form the firmware workflow. The third is an independent
phone-managed media/FTP workflow and is not firmware verification, SUOTA completion,
or reboot acknowledgement.

## OTA information workflow

The phone first marks an OTA-information request pending and asks the ring for its
device/version information. The ordinary device-information callback is emitted before
the OTA policy continues, and its response-integrity result is reported but does not
gate the later metadata path.

The remaining ordered phases are:

1. derive a product-specific firmware/cache location and consult cached metadata;
2. reuse cached JSON while its server-provided expiry remains fresh;
3. otherwise perform a background cleartext metadata request and cache successful JSON;
4. apply optional individual-device eligibility and compare a version component;
5. on the fresh-network path, start automatic-download handling before that eligibility
   and version comparison;
6. download the complete firmware entity into memory and replace the derived local file,
   including when automatic OTA is disabled;
7. compare the written file with an MD5 value supplied by the same metadata source and
   timestamp the cache only when it matches; and
8. in automatic mode, hand a matching file to the file-OTA workflow.

The callback groups are ordinary device information, OTA availability plus metadata and
local path, and OTA-update phase/detail. A non-success metadata response reports no
update with empty metadata. Network exceptions do not have a guaranteed callback.

Static security and correctness facts are: metadata transport is unauthenticated
cleartext HTTP; no signed manifest or firmware signature is visible; MD5 is not an
authenticity check; the entity has no visible size bound; replacement occurs before
digest acceptance; a mismatch is not visibly removed; an information query can mutate
files and initiate download; and fresh-network automatic handling can reach transfer
before the later eligibility/version callback path. No safe model allowlist is
established.

## File OTA / SUOTA workflow

The Binder operation accepts a caller-selected path and an unrestricted integer OTA
type. It immediately reports a transfer-start-shaped status before opening the file,
replaces any prior OTA controller, clears the ordinary command queue, submits the mode
request, and after a fixed delay opens a second GATT connection to the same selected
device.

The secondary connection then:

1. refreshes/discovers services and requires the SUOTA characteristic set;
2. enables the SUOTA status CCCD;
3. allocates the file stream's reported available length and performs one unchecked
   read of the complete file;
4. appends one XOR byte over the original file;
5. writes memory-device, GPIO-map, and patch-length controls;
6. partitions the image into blocks and chunks;
7. sends patch data with write-without-response while broadcasting progress;
8. advances from characteristic-write and status-notification events;
9. attempts end and optional reboot controls; and
10. releases the wake lock, closes the file, disconnects/closes GATT, and may refresh
    the platform GATT cache.

The required roles are memory-device control, GPIO-map control, memory-info status,
patch-length control, patch-data chunks, and status notification. Version,
patch-data-size, MTU, and L2CAP-PSM metadata roles are optional. Exact UUIDs and access
roles are listed in [APK_TRANSPORT_SPEC.md](APK_TRANSPORT_SPEC.md).

The optional metadata identifiers in this build are version `64b4e8b5…`, patch-data
size `42c3dfdd…`, MTU `b7de1eea…`, and L2CAP PSM `61c8849c…`. The superficially
similar `2abc2d8e…` identifier is not present in reviewed owned code and is not part of
this APK specification.

The recovered SUOTA controller state machine is:

| Step | Trigger and action |
|---:|---|
| 0 | queue Device Information and optional metadata reads; after the queue empties, request MTU only when the current value is default or smaller than patch size plus three |
| 1 | reset transfer flags, locally disable status notification, then re-enable it after three seconds |
| 2 | write memory-device control |
| 3 | count memory-device write completion and status `0x10`; the second prerequisite advances to GPIO-map write |
| 4 | GPIO-map write completion sends patch length |
| 5 | patch-length completion or status `0x02` sends/advances chunks, adjusts the final patch length, sends end, or completes when end was already marked sent |

The secondary connection uses `autoConnect=false`, creates but never connects an
RFCOMM socket, waits one second before discovery, and can refresh/rediscover up to ten
times at one-second intervals. It checks every required role and the status CCCD.
Discovery failure maps to communication error; a missing role maps to unsupported
SUOTA. Step 0 runs immediately and again two seconds later while a proceeding action
is broadcast, creating duplicate-read/reset potential. Read callback status and read
submission are ignored; a null Device Information value can leave the queue stalled,
and null optional numeric values can fail during unboxing. Notification and descriptor
submission booleans are ignored, descriptor failure maps to communication error, and
write failure maps to communication error unless reboot is already marked sent. MTU
failure only logs, and disconnect has no guaranteed OTA-error projection.

Status `0x10` is the step-3 prerequisite; `0x02` drives step 5 and can complete after
end is marked sent. Other values are treated as active-SUOTA errors. Values `0x01` and
`0x03` have special handling only for non-SUOTA modes; this firmware manager uses
SUOTA type 1 and therefore treats them as errors.

Memory modes 3 and 4 use different packing helpers but converge on the GPIO-map
operation: set one unsigned 32-bit value at offset zero and attempt the characteristic
write. Every other memory mode logs that it is not set and returns without a write.
The synchronous write boolean is ignored and exceptions are logged without entering a
SUOTA error state. The hardware meaning, safe values, acceptance, and successful
dispatch remain unknown. The OTA type also controls a later reboot branch; other
integers are not rejected at the Binder boundary.

The transfer has no preflight proof of file existence, regular-file type, size, complete
read, signature, digest, model compatibility, or device eligibility before changing
device mode. The full file is materialized in memory. The one-byte XOR is corruption
metadata, not authenticity. Chunk cursor state advances before delivery confirmation;
a rejected dispatch has no immediate local retry or cursor rollback. The end-sent flag
does not require a characteristic or accepted write. Normal completion is
callback-driven: after that flag is set, a later status notification value `0x02`
re-enters the terminal step. The notification is not uniquely correlated to the end
write, so a stale or duplicate value can satisfy the local completion condition. The
dedicated SUOTA error broadcast is not registered by the recovered service receiver,
and the recovered success action cleans up without a final success through
`onGetOtaUpdate`.

## Progress and terminal meaning

`onGetOtaUpdate` carries phase/detail values, not a single transaction result. The
initial success-shaped callback proves neither file readiness nor GATT readiness.
Progress values are forwarded from a broadcast receiver and use coarse integer
division. GATT discovery, CCCD completion, characteristic completion, MTU changes, and
status notifications drive internal state. The later `0x02` status is peripheral input
but lacks operation/end-write correlation; the resulting cleanup/success broadcast is
not proof that the final control was accepted or that reboot succeeded.

## Media FTP boundary

`notifyDownloadFtpFileCompleted` is emitted after either success or exhausted retries
in a separate media-file FTP workflow. It then reports the independent transfer result
through `onNotifyFtpStateInfo`. The same device terminal frame can therefore precede a
success or failure callback; it is not itself a success marker.

The phone FTP task expects six arguments and logs sensitive connection parameters. Its
caller-supplied local path is reused only in failure broadcasts; downloads go under
app-private extension-category directories. Positive-size entries create/truncate a
file and attempt retrieval, while non-positive entries skip creation. Every entry then
attempts remote deletion. Neither retrieval nor deletion booleans are checked, so
source “success” means only that the loop threw no exception. Success is broadcast
before logout, which can subsequently fail. Cancellation between entries broadcasts,
logs out/disconnects, and returns false; cancellation inside the transfer listener can
repeat without reliably aborting and may still be followed by deletion/success.
Initial cancellation is silent, while parse/non-I/O failures can escape the normal
failure broadcast. Login and caught I/O failures report retry/connection metadata.

The firmware digest helper returns empty text for null/invalid/non-file inputs, reads a
valid file in 8 KiB chunks, and normally returns lowercase 32-character MD5. Exceptions
return the accumulator as it stood; a close failure does not erase an already-computed
digest. This remains corruption detection, not authentication.

## Runtime unknowns

Static review cannot establish eligible ring models, firmware compatibility, accepted
memory/GPIO values, safe timing and pacing, negotiated block/chunk limits, status-code
meanings and ordering, peripheral write delivery, reboot acknowledgement, recovery from
interrupted transfer, or post-update identity/state. Those are specified as `unknown`,
not omitted, and require owner-authorized hardware evidence before any implementation
can become runnable.
