# External JRing / 56ff prior art

This is a bibliography and reconciliation queue, not clean-room protocol evidence.
Nothing here grants runtime eligibility, changes the manifest, or permits a packet to
reach a ring. Each claim needs independent comparison against the authorized APK and,
where behavior is involved, owner-hardware evidence.

## Sources

| Source | Public claim relevant to this project | Reconciliation state |
|---|---|---|
| [PulseLoop iOS](https://github.com/saksham2001/PulseLoopiOS) | Direct BLE support for a generic `56ff` JRing family, advertised as `SMART_RING`; health/activity/sleep decoding | compatible-family claim only; untrusted |
| [PulseLoop Android](https://github.com/foureight84/PulseLoopAndroid) | Documents claimed 56ff decoders/configuration: `0x24` combined measurement, `0x16` heart-rate history, `0x10` activity history, `0x0c` device info, `0x48` app ID, `0x02` profile, `0x33` calibration, `0x4b` bind, and `0x3a` keepalive | candidate-by-candidate comparison required; no imported authority |
| [Independent JRing capture write-up](https://jw-tech.fr/en/blog/smart-ring-reverse-engineering) | nRF52840/Wireshark observations of unencrypted 20-byte command-first traffic and several UI-triggered frames | captures and semantics are external; untrusted |
| [UR9 JRing product sheet](https://pdt.static.globalsources.com/IMAGES/PDT/SPEC/601/K1224396601.pdf) | JRing-compatible product claims DA14585, SC7A20, touch/gesture, OTA, and health/activity features | product/model identity and firmware equivalence unknown |

## Rules

1. Do not copy captures, identifiers, credentials, or third-party source into the
   client. Cite an attributable public factual claim only where the license permits.
2. Keep claimed compatible family separate from exact model and firmware scope.
3. A match to the APK's static UUID/frame shape is corroboration, not proof of a field
   meaning, terminal rule, delivery, or safety contract.
4. Route every usable claim through [#58](https://github.com/Pipeliner/jring-client/issues/58), then the clean-room parity manifest and relevant owner-evidence issue before implementation.
