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
| [SR08 JRing manual](https://manuals.plus/m/15d858d0c40176cef74f1a9cb4efb58d5ac8c1dc50c0dfd91032c0226bc88474) and [supplier listing](https://sourcing.hktdc.com/en/Product-Detail/Smart-ring-SR08-1Z03NUEDJ) | SR08 is paired through JRing as `Smart_Ring`; one supplier calls its hardware DA14531, SC7A20, and HX3602 | strong retail-alias candidate; exact firmware and BLE protocol identity unknown |

## Rules

1. Do not copy captures, identifiers, credentials, or third-party source into the
   client. Cite an attributable public factual claim only where the license permits.
2. Keep claimed compatible family separate from exact model and firmware scope.
3. Public implementations may inform a clearly marked unverified candidate decoder,
   simulator comparison, or owner-consented no-write probe. They are not copied into
   this client and do not themselves establish a field meaning, terminal rule,
   delivery, model scope, or safety contract.
4. A match to the APK's static UUID/frame shape is corroboration, not proof. Runtime
   use remains unavailable until the relevant clean-room reconciliation, exact scope,
   and owner-hardware evidence gates pass; vendor writes remain disabled.
5. Route every usable claim through [#58](https://github.com/Pipeliner/jring-client/issues/58), then the clean-room parity manifest and relevant owner-evidence issue before implementation.

`SR08`, `RS08`, and similarly marketed ring names are retail/model labels, never runtime
scope selectors. A visible app association or matching radio/sensor bill of materials
does not prove that a selected ring exposes the APK's exact endpoint, firmware build,
or protocol behavior.
