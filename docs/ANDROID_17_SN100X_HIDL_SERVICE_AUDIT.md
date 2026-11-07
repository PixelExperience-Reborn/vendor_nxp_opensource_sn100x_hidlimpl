# PixelExperience-Reborn Android 17 — matrix row 173: SN100x HIDL NFC services

**Reviewed:** 2026-11-07. **ROM goal:** independent PixelExperience-Reborn Android 17, future POCO F5 Pro / Redmi K60 **mondrian**, SM8475. **Scope:** static source and manifest ownership audit; no build server, test device, vendor partition image, firmware update, or HAL runtime result.

## Engineering decision

**Do not activate archived `vendor/nxp/opensource/sn100x/hidlimpl` on Android 17.** It is a historical 2020 HIDL wrapper for the 2022-era SN100x native library audited in row 172. Preserve the official AOSP17 source owners:
- `platform/hardware/nxp/nfc`, pinned AOSP17 NFC native HAL and modern system/vendor AIDL source;
- `platform/packages/modules/Nfc`, NFC Mainline and `com.android.nfcservices`;
- `platform/system/secure_element`, modern SE/OMAPI owners.

NXP 17.07.00 AIDL V2 is a *comparison source*, not a reason to replace the official Git tree. The official AOSP17 `hardware/nxp/nfc` already declares `android.hardware.nfc2-service.nxp`, AIDL V2 `INfc/default` plus vendor AIDL V1 `INxpNfc/default`, as verified by row 172's Git CI. Neither source presence nor a successful static audit proves the chosen `mondrian` hardware runs that HAL. Final product must select only one system NFC HAL, with exact VINTF/SELinux, vendor compatibility and firmware.

## Exact source provenance

| Source | Immutable reference | Ownership |
| --- | --- | --- |
| PE archived SN100x service wrappers | `PixelExperience-Reborn/vendor_nxp_opensource_sn100x_hidlimpl`, `seventeen` commit `f0c90061cd98bfba93e21d3a82ad10c3fa86d5bf`, tree `79bcba375cb26075abc393e23781439ec6dd468e`, dated 2020-05-21 | HIDL 1.2 core + NXP extension service; **18 file blobs** |
| PE archived PN5xx service wrappers (row 171) | `PixelExperience-Reborn/vendor_nxp_opensource_pn5xx_hidlimpl`, `seventeen` commit `a210f5e90e6ce7326f0cc5fcfda40ca63d55373e`, tree `8dce70df4a27e314065ff18433b6162a8ff41fd4` | HIDL 1.2 core with distinct NXP extensions, **20 file blobs** |
| PE archived SN100x native HAL library (row 172) | `PixelExperience-Reborn/vendor_nxp_opensource_sn100x_halimpl`, `seventeen` commit `4febf025eb375939005779f133b6723e449062f0`, tree `af032a30031fd5c27f5435cf8792c7f1cc22688d` | Old `nfc_nci.nqx.default.hw`, `se_nq_extn_client`, eSE/JCOP/LS clients, Soong parser, sample NFC configuration |
| Official AOSP17 NXP NFC HAL | `android-17.0.0_r1` commit `68931d93d3b2ccfc71553cb03088fe5d6fb5dd30`, tree `8386a3c67e07f5fe492c92d1888c256bbc37d48b` | `hardware/nxp/nfc`: official Soong service, modern NFC AIDL V2 + vendor AIDL V1 |
| Current NXP Android17 source | `NXPNFCProject/nfcandroid_nfc_hidlimpl` `br_ar_17_aosp_mainline`, commit `debec247cea5570d259db3138124201e3769a728`, tree `31be748946aaf58dcf86034804db69c53a4ac3a7`, release 17.07.00 | Vendor source reference, not a separate selected tree |

## Actual old HIDL service startup and dependencies

| Old Soong service | Native library + additional linked modules | Registration and init | Risk |
| --- | --- | --- | --- |
| `vendor.nxp.hardware.nfc@1.2-service` | `nfc_nci.nqx.default.hw`; `android.hardware.nfc@1.0/@1.1/@1.2`; `vendor.nxp.hardware.nfc@1.0/@1.1`; `libhidlbase` | `1.2/default/service.cpp`: `android.hardware.nfc::V1_2::INfc` and NXP `V1_1::INqNfc` both `registerAsService()`; **both** registration failures fatal; `nqnfc_1_2_hal_service`, `class hal`, `user/group nfc` | HIDL system NFC, direct old vendor HAL library. Not AIDL |
| `vendor.nxp.hardware.nfc@2.0-service` | `nfc_nci.nqx.default.hw`, **`se_nq_extn_client`**; NFC HIDL 1.0–1.2, NXP HIDL 2.0, `libhidlbase` | `2.0/default/service.cpp`: **still** `android.hardware.nfc::V1_2::INfc`, vendor `V2_0::INqNfc`; main registration fatal, vendor registration error **logged only**; `nqnfc_2_0_hal_service`, `class hal`, `user/group nfc` | Vendor 2.0 is not system AIDL V2; old eSE state/control APIs |
| Both | Shared old Soong HIDL graph from row172 | `/vendor/bin/hw/`, `hwbinder` conventions | Adding a parallel NFC AIDL service may produce inconsistent VINTF, service discovery, system NFC ownership and SE routing |

**Important source precision:** Unlike row 171's PN5xx wrapper, the SN100x `2.0/default/service.cpp` does **not** register `vendor.nxp.nxpnfclegacy@1.0` and does **not** contain `NxpNfcLegacy.cpp`. It links `se_nq_extn_client` instead. Do not claim a legacy raw NCI Binder service exists here. The separate `1.2/NxpNfcService.cpp` in the *native HAL repository* (row172), not this 18-blob service wrapper repo, calls `initializeEseClient`, `checkEseClientUpdate` and `perform_eSEClientUpdate` on startup. Those sources are important **risk evidence**, but do not prove the archived `vendor.nxp.hardware.nfc@2.0-service` executes these calls. Verify actual product build and service selection before making any assertion about boot-time eSE updates.

### Exact cross-archive comparison (Git blob identity, not similarity judgment)

The 18 SN100x HIDL service blobs have the same 18 paths in the PN5xx wrapper. **14 of 18 blob IDs match byte-for-byte**. Four differ:

1. `1.2/default/Nfc.cpp`: source differs from PN5xx's 1.2 NFC class; NFC core still HIDL 1.2. Confirm reset and other behavior before treating the variants as interchangeable.
2. `2.0/default/Android.bp`: SN100x adds `se_nq_extn_client` and omits PN5xx `vendor.nxp.nxpnfclegacy@1.0` dependency.
3. `2.0/default/NqNfc.cpp`: SN100x vendor `resetEse(uint64_t resetType)` **forwards `resetType`** to `phNxpNciHal_resetEse(resetType)`, unlike the PN5xx wrapper which ignores it. SN100x also implements `setEseUpdateState` through legacy eSE client state operations, so consider authorization and data integrity.
4. `2.0/default/service.cpp`: SN100x registers system NFC and NXP HIDL 2.0 only; PN5xx additionally registers `INxpNfcLegacy`.

The PN5xx wrapper has two extra `2.0/default/NxpNfcLegacy.{cpp,h}` blobs that are **absent** from SN100x. Although two archives overlap, their eSE-reset semantics and service graphs are not identical. Never deduplicate/merge them as a build convenience.

### Source security boundary

- `1.2/default/NqNfc.cpp` implements `ioctl(uint64_t,... hidl_vec<uint8_t>& inputData)`, takes `&inputData[0]` and copies a native `nfc_nci_IoctlInOutData_t` without an obvious length check in this wrapper. **Potential memory-safety review item** if untrusted or undersized Binder input can reach it. This is a static observation, not a demonstrated exploit or a claim that it is shipped. Do not reexpose this API.
- `2.0/default/NqNfc.cpp` exposes vendor parameters, eSE reset, JCOP/LS update-state transitions and transit configuration; require tightly scoped caller/SELinux checks for the modern equivalent. HIDL-to-AIDL conversion of an API signature does not itself prove safe authorization.
- In 2.0, a failed vendor service registration can be logged while the process remains in the Binder loop. This is an integration monitoring problem, not necessarily a security vulnerability.
- Avoid old NFC/SE firmware download, arbitrary NFCC configuration, P73/JCOP update, boot-time eSE mutation and broad permissions. AOSP17 NFC Mainline, OMAPI and vendor binaries must remain within modern access-control boundaries.

## Current Android17 owner versus new NXP vendor code

The official AOSP17 `hardware/nxp/nfc` contains **both** `android.hardware.nfc-service.nxp` and `android.hardware.nfc2-service.nxp` source modules and the exact NFC AIDL V2 VINTF fragment. NXP 17.07.00's branch contains `android.hardware.nfc2-service.nxp` and its native Binder service. **Only the product-selected compatible variant should be installed/registered**, alongside at most one `vendor.nxp.nxpnfc_aidl.INxpNfc/default`. Do not confuse source module presence with actual installed binaries on mondrian.

The previous pinned AOSP17 vs current vendor `snxxx/` comparison found 168 shared files (84 differing blobs), zero NXP-only paths and 118 AOSP-only paths. These differences justify **pinpoint diff and semantic/ABI review**, not replacing the official source tree wholesale.

## Device-specific engineering and acceptance gates

1. Identify the real mondrian NFCC SKU/chip, firmware/driver node, vendor HAL binary (ELF `DT_NEEDED` and symbol version requirements), VINTF declaration, NFC service/SE property configuration and eSE/UICC topology from matched Xiaomi firmware or authorized device diagnostics. **Do not infer the NFCC from the string SN100x, a PN81T example, or an unrelated custom ROM**.
2. Preserve source ownership and the new independent PE-Reborn product/device design; LF52406 LineageOS trees may be used only as an *exceptional read-only* hardware evidence source, not a copied base.
3. Validate the selected official AOSP17 NXP HAL service, actual AIDL version, frozen NDK hash/API, Soong build, service binary and correct `INfc/default` registration. No duplicate HIDL/AIDL HALs or conflicting VINTF fragments.
4. Validate SELinux enforcing, Binder caller identity, property access, SE reset/transit configuration, OMAPI access rules and UICC routing before granting capabilities.
5. Physical mondrian tests: NFC tag read/write, HCE/card emulation and payment *only when supported and authorized*, SE/OMAPI, RF/calibration, secure resets/rollback and low power/standby/reboot/OTA, plus CTS/VTS. No real hardware tests are possible from this source-only environment.

## Recorded GitHub changes

A review-only branch adds this pinned audit, deterministic four-tree comparison checker and GitHub Actions. The PE-Reborn manifest working branch rejects historical `vendor/nxp/opensource/sn100x/hidlimpl` by path and repo name with independent negative tests. The audited matrix row is updated. **No old source/firmware/VINTF/SE mutations are staged into `default.xml`**. Historical `seventeen` remains untouched.

**Limits:** CI tests source and manifest identities only. It does not prove NFC system build or hardware functionality.
