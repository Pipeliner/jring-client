# Clean-room APK session, binding, queue, and race specification

Status: complete publication of the currently recovered 33 transitions, six binding
reactions, and 22 race findings. These populations are not yet proven exhaustive state
machines.

The APK does not have one unified authorization/session state. SDK validation, device
policy, Android link state, service discovery, notification setup, startup clock sync,
vendor binding, classic bonding, command queue state, and reconnect state are separate.

## Recovered transitions — 33

| Code | Lane | Prerequisite | Source effect | Result |
|---|---|---|---|---|
| `default_sdk_status` | SDK validation | — | shared SDK status starts as 200 | service created |
| `remembered_target_reconnect` | reconnect | service created | remembered target may reconnect before callback registration | reconnect started |
| `register_bundled_credential_callback` | callback registration | — | install global callback, then cache/network branch with bundled credentials | callback registered |
| `register_caller_credential_callback` | callback registration | — | install global callback, then cache/network branch with caller credentials | callback registered |
| `report_cached_sdk_status` | SDK validation | callback registered | fresh timestamp reports shared status without network | cached result reported |
| `request_bundled_sdk_validation` | SDK validation | callback registered | expired cache posts developer validation; source logs request body | validation pending |
| `request_caller_sdk_validation` | SDK validation | callback registered | expired cache posts caller-provided validation; source logs request body | validation pending |
| `apply_sdk_validation_result` | SDK validation | validation pending | successful body updates shared status/expiry; transport error does not replace status | result applied |
| `check_manual_connect_gate` | SDK validation | service created | manual connect reads current status without awaiting validation | gate checked |
| `start_gatt_connect` | BLE link | gate checked | status-200 branch persists target and starts reconnect flow | GATT connecting |
| `observe_gatt_link` | BLE link | GATT connecting | Android link is connected but vendor route is not ready | link connected |
| `start_service_discovery` | service discovery | link connected | retry-managed discovery starts; no effective initial GATT-connect timeout recovered | discovery pending |
| `retry_service_discovery` | service discovery | discovery pending | at most three attempts, each with 30-second timer; exhaustion enters recovery | discovery retrying |
| `accept_services` | service discovery | discovery pending | clear command queue before useful-characteristic check | services accepted/queue cleared |
| `delay_characteristic_initialization` | MAIN notification | services accepted | delay primary-characteristic initialization 500 ms | initialization delayed |
| `accept_notification_dispatch` | MAIN notification | initialization delayed | local enable and descriptor-write submission return true | dispatch accepted |
| `report_source_connected` | BLE link | dispatch accepted | report state 2 before descriptor callback and device-policy result | source connected reported |
| `check_device_policy_cache` | device policy | source connected | inspect per-target flag and fixed 24-hour timestamp | policy cache checked |
| `report_cached_device_allow` | device policy | policy cache checked | cached zero flag reports shared SDK status | cached allow reported |
| `request_device_policy` | device policy | policy cache checked | post target and phone identifiers; source logs request body | policy pending |
| `record_device_allow` | device policy | policy pending | zero/missing flag keeps link open; callback reports shared SDK status | allow recorded |
| `close_on_device_deny` | device policy | policy pending | nonzero flag closes link; callback does not expose flag unambiguously | deny closes link |
| `handle_descriptor_special_failure` | MAIN notification | dispatch accepted | one special status disconnects and refreshes GATT cache | special failure |
| `observe_descriptor_other_result` | MAIN notification | dispatch accepted | all non-special statuses continue, including other failures | other result observed |
| `queue_startup_clock_sync` | startup clock | descriptor other result | queue opcode-01 time mutation; total/raw offset handling differs | clock sync queued |
| `observe_binding_notification` | vendor binding | — | observe source-labeled action and neutral second value | binding notification observed |
| `send_binding_start` | vendor binding | binding notification | init-zero branch queues action 1 with tail `0,1` | start sent |
| `send_binding_success` | vendor binding | binding notification | ACK branch queues action 4 with tail `0,1` | success sent |
| `confirm_vendor_binding` | vendor binding | binding notification | action 4 is logged as confirmation without proving owner identity | binding confirmed by source label |
| `send_vendor_unbind` | vendor binding | — | explicit UI path queues action 5 with tail `0,1` | unbind sent |
| `acknowledge_vendor_unbound` | vendor binding | binding notification | actions 3/6 clear local sync state | unbound acknowledged by source label |
| `record_disconnect` | BLE link | — | clear or retain target according to separate source policy | disconnected |
| `schedule_reconnect` | reconnect | disconnected | non-user disconnect schedules delayed reconnect | reconnect scheduled |

None of the “allow,” “success,” “confirmation,” or “acknowledged” source labels proves
physical owner identity or hardware behavior.

## Binding reaction table — 6

| Inbound source code/action | Required second value | Outbound code/action | Local effect |
|---|---:|---|---|
| `0` / init | `0` | `1` / app-start | queue source-labeled app-start |
| `2` / ACK | `0` | `4` / success | queue source-labeled success |
| `3` / ACK-cancel | `0` | — | clear sync state; signal local unbind completion |
| `4` / success | `0` | — | record source-labeled confirmation |
| `6` / unbind-ACK | `0` | — | clear sync state; signal local unbind completion |
| — | — | `5` / unbind | explicit app UI path |

The second value is only structurally constrained. Its meaning remains unknown.

## Recovered races — 22

| Code | Lanes | Observation | Unsafe inference |
|---|---|---|---|
| `concurrent_registration_replaces_callback_slot` | callback registration, SDK validation | each registration replaces one shared callback before independent cache/network work | completion returns to the callback that launched it |
| `future_validation_timestamp_passes_cache_check` | SDK validation | future source timestamp is accepted and reports initialized status | cache hit proves a fresh decision |
| `startup_reconnect_precedes_callback_registration` | reconnect, registration | remembered reconnect may start before callback installation | registration owns or authorizes the connection |
| `manual_connect_does_not_await_sdk_validation` | validation, BLE link | connect reads shared status while validation may still be pending | connect implies a fresh cloud decision |
| `sdk_validation_transport_error_does_not_replace_runtime_gate` | validation | transport failure is reported without replacing initialized gate | reported error necessarily blocks connect |
| `source_connected_precedes_descriptor_callback` | BLE link, notification | source state 2 follows descriptor dispatch acceptance | connected means descriptor acknowledgement |
| `device_authorization_starts_after_source_connected` | BLE link, policy | device policy begins after source-connected callback | connected proves policy approval |
| `device_authorization_callback_conflates_status_domains` | validation, policy | callback can report HTTP/shared SDK status rather than policy flag | callback is reliable owner authorization |
| `conditional_dynamic_descriptor_writes_are_not_serialized` | notification | primary and dynamic notification setup can overlap | descriptor callback identifies one ordered transaction |
| `descriptor_non_special_status_triggers_clock_sync` | notification, startup clock | every non-special status queues clock sync | clock write proves descriptor success |
| `binding_response_can_interleave_with_command_queue` | binding, command queue | binding responses use the ordinary queue | binding serializes all session actions |
| `callbacks_are_not_connection_generation_bound` | link, notification, binding | callbacks are not uniformly generation-bound | late callback belongs to current link |
| `late_cloud_result_can_affect_a_later_connection` | policy, reconnect | cloud completion can arrive after disconnect/reconnect | result applies to newest connection |
| `classic_bonding_is_orthogonal_to_vendor_binding` | classic bond, vendor binding | Android classic bonding occurs in separate app/audio paths | OS bond proves vendor binding or vice versa |
| `discovery_exhaustion_enters_recovery` | discovery, reconnect | three attempts with 30-second timer precede recovery | one failure is final or one success proves endpoints |
| `missing_endpoints_enter_delayed_recovery` | discovery, reconnect | service discovery can succeed before required characteristics are found | Android service callback establishes vendor route |
| `descriptor_dispatch_false_disconnects` | notification, reconnect | synchronous dispatch rejection schedules disconnect | failed dispatch is device rejection |
| `stale_gatt_callback_can_target_current_link` | link, discovery, notification | old GATT callback can act through current shared-link field | closing old link prevents stale effects |
| `synchronous_write_false_retries_up_to_31_calls` | command queue | synchronous write rejection retries up to 31 calls with blocking delays | blind retry is safe because call returned false |
| `write_callback_status_is_ignored` | command queue | Android callback releases send gate without status check | callback arrival proves write success |
| `accepted_write_without_callback_has_uncertain_outcome` | command queue | accepted dispatch can lose callback | timeout proves command did not mutate ring |
| `dormant_response_matching_is_global_not_operation_bound` | command queue | dormant response wait uses one global completion signal | any recognized notification is the pending response |

## State variables required by the final specification

The final state model must track, independently: callback generation, SDK-validation
cache/status/request, device-policy cache/status/request, selected/remembered target,
Android GATT object generation, link state, discovery attempt/timer, required endpoint
presence, notification dispatch, descriptor result, startup-clock write, vendor-binding
state, Android classic bond/profile state, command queue/send gate/pending payload,
write invocation/callback/status, response ownership, disconnect cause, and reconnect
generation.

Each transition still needs exact trigger, guard, prior-state predicate, mutation order,
callback order, timeout, retry, cleanup, and error/exception behavior confirmed against
complete DEX/smali evidence. The 33/6/22 ledgers are recovered facts, not proof that no
other transitions or races exist.
