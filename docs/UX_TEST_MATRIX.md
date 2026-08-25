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
| Protocol maintainer | Instruction review finds an ordered 104-opcode comparison chain | Separate 85 targets, 125 syntactic invokes, 124 reachable invokes, 99 callback-bearing opcodes, and five no-callback opcodes | Never call any count “wire families”; meanings and hardware behavior remain unresolved |
| Security reviewer | A fallback file exists but the warned receiver body is absent | Name the body as unavailable and keep its branch claims unresolved | Counterpart state is `fallback_body_unavailable`; no completeness promotion |
| OTA reviewer | Instruction review resolves a decompiler selector divergence | State only the reviewed local branches; refuse selector meaning, safe values, delivery, or device acceptance | Historical comparison remains divergent; bounded local fact is confirmed; hardware block remains |
| Reliability reviewer | OTA cursor or terminal flag advances after a write attempt | Do not translate local state into delivery or acknowledgement | Rejected chunk dispatch has no immediate local retry; local completion is not peripheral acknowledgement |
| Runtime reviewer | An all-DEX direct-reference search finds no dial-transfer constructor | Say direct construction was not observed, while naming reflection/native/dynamic limits | Review is `inconclusive`, not runtime dormancy proof |
| Privacy reviewer | A bounded fact is shown in JSON | Receive only sanitized scope, state, span count, observation, and limitations | No DEX digest, descriptor, prototype, offset, fingerprint, path, source, or disassembly appears |
| Parity reviewer | Hundreds of Bluetooth-facing methods are classified | Count only exact AIDL declarations as interface rows | Request/callback ledgers remain 112/105 with zero missing rows |
| Android maintainer | System Bluetooth actions are registered through process-local broadcasting | Show the registration-domain mismatch and unhandled cases | Never claim those events are delivered without an observed bridge |
| Security reviewer | A dynamic system receiver accepts app actions without sender permission | Name the permission and teardown gaps without reproducing action strings | Treat as source-app attack surface; JRing recreates none of it |
| Security reviewer | The source app has an exported Bluetooth controller and bundled SDK configuration | Expose only component/asset counts and risk boundaries | Never expose component names, actions, credentials, or configuration values |
| Native reviewer | All three packaged JNI roots resolve to image/wallpaper processing | Report the bounded rooted graph and keep seven unmatched declarations and whole-ELF instructions visible | Native Bluetooth absence remains unestablished |
| Runtime reviewer | Direct dial construction is absent but reflection, Binder, and resource tokens exist | Report activation as inconclusive | Never call the implementation dormant or unreachable |
| Runtime reviewer | All owned reflection calls resolve to constant Android helper targets | Close only that bounded reflection route | Runtime-generated and exhaustive activation remain unresolved |
| Runtime reviewer | Reviewed Binder, service, resource, and navigation paths never activate the standalone dial class | Report the bounded static no-edge result | Runtime reachability remains inconclusive |
| Protocol contributor | Sixteen non-opcode callbacks previously have no Python state | Classify 14 dispatch surfaces and two undispatched declarations | Zero unclassified rows; no callback becomes runnable or hardware-eligible |
| Privacy reviewer | Platform callbacks can contain raw GATT, scan, network, cloud, or file data | Expose only closed privacy categories | No callback values, identifiers, credentials, or paths enter coverage output |
| Sensor user | A motion frame carries a ninth signed channel in its final byte pair | Decode all nine neutral channels | Never drop bytes 18–19 or invent axis meanings |
| Protocol contributor | A codec count is assigned by name-set membership | Resolve every codec row through an immutable typed locator | 85/85 request and 86/86 callback rows resolve; shared-family ambiguity stays visible |
| Transport reviewer | Interface routes are mistaken for fixed BLE packets | Partition all 112 rows into deterministic main/raw, stateful, dynamic, descriptor, DFU, and no-packet shapes | 79+6+1+1+1+1+23 reconciles exactly; no route is runnable |
| Privacy-sensitive protocol reviewer | Shared opcodes and completion-shaped names look like acknowledgements | Preserve the App-ID event candidate, Phone-MAC collision, disjoint Wi-Fi state candidate, and dual-outcome FTP projection as separate non-terminal states | No identifier equality, credential use, connection, transfer, response, or hardware claim; default output remains aggregate-only |
| Privacy-sensitive contact owner | A fingerprint notification is near an outbound contact batch | Describe only the conditional app-local reverse-sync topology and redact records | No acknowledgement, response, terminal, private-store reproduction, or runnable path; a local contact change can initiate the same outbound sequence |
| Accessibility or automation user | A successful report and zero missing AIDL rows look like complete Bluetooth parity | Lead human output with the negative verdict and expose a top-level JSON parity object | `ok: true` means report success only; scoped row accounting cannot satisfy semantic, live, or hardware gates |
| History user | Local quiet follows generic history data | Label the local end projection incomplete instead of saying the device finished | Only detail wire/metadata evidence can confirm completion; a caller limit emits no end |

Across every row, logs and errors omit Bluetooth addresses, cloud identifiers, frame
bytes, raw measurements, and decompiled-source details. Simulation provenance remains
visible, and no fake result becomes a hardware-support claim.
