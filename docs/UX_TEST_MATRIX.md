# Adversarial vendor-connection UX test matrix

Status: design constraints; fake-only until owner hardware evidence is approved

These scenarios keep recovered control-flow domains separate. They do not claim a live
vendor implementation or hardware verification.

| User or context | Adversarial condition | Required human result | Required machine state |
|---|---|---|---|
| First-time Linux user | Link connects but endpoints are still being checked | Say “Bluetooth link connected; checking vendor endpoints,” never “ready” | `link_connected=true`; `transaction_ready=false`; later stages remain false or pending |
| Screen-reader user | Several stages change quickly | Announce one ordered, task-named change at a time; do not rely on color or a spinner | Stable stage names and monotonic operation generation |
| Automation author | Notification activation returns before descriptor evidence | Report activation only; never claim CCCD acknowledgement | `subscription_activated=true`; `cccd_acknowledged=unknown` |
| Privacy-sensitive owner | Cloud policy is unavailable | Explain that cloud policy was not checked and no credentials were replayed | Cloud state is separate and contains no endpoint, account, or device identifier |
| Offline owner | Developer validation has no network | Do not block passive/simulated use or imply the ring rejected ownership | `developer_policy=unavailable`; transport state unchanged |
| Owner during delayed gear policy | BLE looks ready before policy returns | Keep policy visibly pending; a later denial names policy as the disconnect reason | `device_policy=pending` cannot promote transaction readiness |
| Previously bound owner | Android reports bonded but `4b` state is unknown | Present OS bond and application binding as different facts | Independent `android_bond` and `application_binding` fields |
| User with classic Bluetooth disabled | Vendor GATT is available | Do not request OS bonding merely to read vendor GATT | Android bond remains `not_required` for the transaction |
| Slow adapter | Service discovery times out | Name endpoint discovery, retain a bounded deadline, and offer reconnect rather than a command retry | No write token exists; outcome is `aborted` |
| Firmware with duplicate UUIDs | More than one candidate route exists | Refuse with a compatibility explanation; do not choose by UUID alone | Route preflight fails before subscription or write |
| Disconnect/reconnect race | Old descriptor or write callback arrives late | Ignore it silently or note a stale event in redacted debug output | Generation mismatch cannot advance current state |
| Fast peripheral | Response arrives before the write callback | Keep it bounded to the current operation and wait for the write outcome | Early response is buffered with generation and operation token |
| Noisy peripheral | Unrelated notification arrives while waiting | Keep waiting without extending the deadline | Matcher rejects it; deadline is unchanged |
| Accepted write, lost callback | Deadline expires after possible dispatch | Say “the ring may have received this; it was not repeated; reconnect before continuing” | `outcome=uncertain`; connection tainted; retries zero |
| Definite pre-dispatch failure | Transport rejects the write before dispatch | Say the operation was not sent and may be attempted after the cause is fixed | `outcome=aborted`; no delivery ambiguity |
| User cancels during write | Cancellation races transport completion | Finish bounded cleanup and state whether dispatch was possible | Pre-dispatch cancellation is aborted; otherwise uncertain and tainted |
| Cleanup failure | Unsubscribe or close does not confirm | Do not report a clean reusable session | Cleanup is bounded; connection remains tainted |
| Startup clock owner | Notification setup completes | Never write time implicitly; explain that time sync is a separate explicit mutation | No opcode-`01` write without dedicated consent |
| Binding prompt user | Device requests a `4b` transition | Name the binding action and require its own consent; do not cite cloud or OS bond as approval | Binding transition has its own token and audit state |
| Input-mapping user | Connection is uncertain or policy changes | Disarm input immediately and emit no catch-up clicks | Input eligibility requires current generation and confirmed source state |
| Protocol maintainer | Structured and fallback decompiler output agree at a warning site | Say “same-tool surface corroboration,” never “validated” or “resolved” | Semantic correctness stays false until bounded instruction review |
| Security reviewer | A fallback file exists but the warned receiver body is absent | Name the body as unavailable and keep its branch claims unresolved | Counterpart state is `fallback_body_unavailable`; no completeness promotion |
| OTA reviewer | Decompiler modes disagree on selector/write control flow | Refuse a selector meaning and retain the hardware block | Comparison is divergent; instruction review is not performed |

Across every row, logs and errors omit Bluetooth addresses, cloud identifiers, frame
bytes, raw measurements, and decompiled-source details. Simulation provenance remains
visible, and no fake result becomes a hardware-support claim.
