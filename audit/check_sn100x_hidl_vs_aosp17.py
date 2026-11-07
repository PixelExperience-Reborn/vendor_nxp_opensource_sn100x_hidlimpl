#!/usr/bin/env python3
"""PE-Reborn AOSP17 matrix row 173 — immutable NFC HIDL/AIDL source gate.

This is a source/manifest audit, NOT Soong, vendor ABI, device VINTF or NFC testing.
Input order: legacy SN100x HIDL, legacy PN5xx HIDL, old SN100x HAL,
             official AOSP17 NXP NFC HAL, newer NXP17 HAL, PE manifest.
"""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

OLD_SN_SHA = "f0c90061cd98bfba93e21d3a82ad10c3fa86d5bf"
OLD_SN_TREE = "79bcba375cb26075abc393e23781439ec6dd468e"
OLD_PN_SHA = "a210f5e90e6ce7326f0cc5fcfda40ca63d55373e"
OLD_PN_TREE = "8dce70df4a27e314065ff18433b6162a8ff41fd4"
OLD_HAL_SHA = "4febf025eb375939005779f133b6723e449062f0"
OLD_HAL_TREE = "af032a30031fd5c27f5435cf8792c7f1cc22688d"
OFF_SHA = "68931d93d3b2ccfc71553cb03088fe5d6fb5dd30"
OFF_TREE = "8386a3c67e07f5fe492c92d1888c256bbc37d48b"
NXP_SHA = "debec247cea5570d259db3138124201e3769a728"
NXP_TREE = "31be748946aaf58dcf86034804db69c53a4ac3a7"
OLD_PATH = "vendor/nxp/opensource/sn100x/hidlimpl"
OLD_REPO = "vendor_nxp_opensource_sn100x_hidlimpl"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True, stderr=subprocess.PIPE).strip()


def pin(root, ref, commit_sha, tree_sha, title):
    commit = git(root, "rev-parse", f"{ref}^{{commit}}")
    require(commit == commit_sha, f"{title}: unexpected SHA {commit}")
    tree = git(root, "rev-parse", f"{commit}^{{tree}}")
    require(tree == tree_sha, f"{title}: unexpected tree {tree}")
    return commit


def show(root, commit, path):
    return git(root, "show", f"{commit}:{path}")


def blobs(root, commit):
    result = {}
    for line in git(root, "ls-tree", "-r", commit).splitlines():
        meta, name = line.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind == "blob":
            result[name] = sha
    return result


def legacy_compare(old_sn, old_pn):
    sn = pin(old_sn, "refs/remotes/origin/seventeen",
             OLD_SN_SHA, OLD_SN_TREE, "SN100x 2020 HIDL wrapper")
    pn = pin(old_pn, "refs/remotes/origin/seventeen",
             OLD_PN_SHA, OLD_PN_TREE, "PN5xx 2020 HIDL wrapper")
    sn_blobs, pn_blobs = blobs(old_sn, sn), blobs(old_pn, pn)
    common = set(sn_blobs) & set(pn_blobs)
    changed = {p for p in common if sn_blobs[p] != pn_blobs[p]}
    require(len(sn_blobs) == 18 and len(pn_blobs) == 20
            and len(common) == 18 and len(common - changed) == 14,
            "archived SN100x/PN5xx HIDL file identities changed")
    require(changed == {
        "1.2/default/Nfc.cpp", "2.0/default/Android.bp",
        "2.0/default/NqNfc.cpp", "2.0/default/service.cpp",
    }, f"unexpected historical SN100x vs PN5xx delta: {sorted(changed)}")
    require(set(pn_blobs) - set(sn_blobs) == {
        "2.0/default/NxpNfcLegacy.cpp",
        "2.0/default/NxpNfcLegacy.h",
    }, "SN100x vs PN5xx legacy interface footprint changed")
    print("PASS: exactly 18 SN100x HIDL blobs, 14 identical to PN5xx, four changed")
    print("PASS: SN100x intentionally excludes PN5xx NxpNfcLegacy API")

    for version, ext in (("1.2", "1.1"), ("2.0", "2.0")):
        module = f"vendor.nxp.hardware.nfc@{version}-service"
        bp = show(old_sn, sn, f"{version}/default/Android.bp")
        svc = show(old_sn, sn, f"{version}/default/service.cpp")
        rc = show(old_sn, sn,
                  f"{version}/default/{module}.rc")
        for item in (
            f'name: "{module}"',
            f'init_rc: ["{module}.rc"]',
            'defaults: ["hidl_defaults"]',
            '"nfc_nci.nqx.default.hw"',
            '"android.hardware.nfc@1.0"',
            '"android.hardware.nfc@1.1"',
            '"android.hardware.nfc@1.2"',
            f'"vendor.nxp.hardware.nfc@{ext}"',
        ):
            require(item in bp,
                    f"legacy {version} HIDL Soong linkage changed: {item}")
        require("using android::hardware::nfc::V1_2::INfc" in svc
                and f"vendor::nxp::hardware::nfc::V{ext.replace('.', '_')}::INqNfc"
                in svc
                and "nfc_service->registerAsService()" in svc
                and "nq_nfc_service->registerAsService()" in svc
                and "configureRpcThreadpool(1, true" in svc,
                f"legacy {version} HIDL service registration changed")
        require(f"service nqnfc_{version.replace('.', '_')}_hal_service"
                in rc and f"/vendor/bin/hw/{module}" in rc
                and "class hal" in rc and "user nfc" in rc
                and "group nfc" in rc,
                f"legacy {version} init service changed")
    bp2 = show(old_sn, sn, "2.0/default/Android.bp")
    service2 = show(old_sn, sn, "2.0/default/service.cpp")
    service1 = show(old_sn, sn, "1.2/default/service.cpp")
    require('"se_nq_extn_client"' in bp2
            and '"vendor.nxp.nxpnfclegacy@1.0"' not in bp2,
            "SN100x 2.0 eSE-client/HIDL distinction changed")
    require("INxpNfcLegacy" not in service2
            and "nxp_nfc_legacy_service->registerAsService()" not in service2,
            "SN100x unexpectedly registered legacy raw-NCI service")
    require(service1.count("LOG_ALWAYS_FATAL_IF(status != OK") == 2,
            "SN100x HIDL1.2 vendor registration is no longer fatal")
    require("LOG_ALWAYS_FATAL_IF(status != OK" in service2
            and 'ALOGE_IF(status != OK' in service2,
            "SN100x HIDL2.0 vendor registration observability changed")
    vendor = show(old_sn, sn, "2.0/default/NqNfc.cpp")
    pn_vendor = show(old_pn, pn, "2.0/default/NqNfc.cpp")
    require("NqNfc::resetEse(uint64_t resetType)" in vendor
            and "phNxpNciHal_resetEse(resetType)" in vendor,
            "SN100x eSE hard-reset parameter semantics changed")
    require("NqNfc::resetEse(uint64_t /* resetType */)" in pn_vendor
            and "phNxpNciHal_resetEse()" in pn_vendor,
            "PN5xx ignored eSE resetType semantics changed")
    for method in ("setEseUpdateState(", "seteSEClientState(",
                   "eSEClientUpdate_NFC_Thread(", "setNxpTransitConfig("):
        require(method in vendor,
                f"SN100x vendor eSE-update control changed: {method}")
    ioctl = show(old_sn, sn, "1.2/default/NqNfc.cpp")
    require("NqNfc::ioctl(uint64_t ioctlType" in ioctl
            and "&inputData[0]" in ioctl
            and "memcpy(&inpOutData" in ioctl
            and "inputData.size()" not in ioctl,
            "old HIDL ioctl wrapper size-validation needs re-audit")
    print("PASS: both SN100x wrappers register system NFC HIDL1.2, NOT AIDL V2")
    print("PASS: HIDL2.0 uses eSE client; PN5xx legacy raw-NCI service excluded")
    print("PASS: SN100x passes resetType, while PN5xx ignores it")
    print("WARN: archived HIDL1.2 ioctl wrapper lacks visible input size guard")
    print("WARN: this is a code-review signal, not an exploit demonstration")


def old_hal_source(root):
    ref = pin(root, "refs/remotes/origin/seventeen",
              OLD_HAL_SHA, OLD_HAL_TREE, "SN100x 2022 native dependency")
    bp = show(root, ref, "SN100x/Android.bp")
    base = show(root, ref, "Android.bp")
    make = show(root, ref, "nfc_vendor_product.mk")
    startup = show(root, ref, "1.2/NxpNfcService.cpp")
    for token in ("nfc_nci.nqx.default.hw", "android.hardware.nfc@1.2",
                  "vendor.nxp.hardware.nfc@2.0",
                  "android.hardware.secure_element@1.0"):
        require(token in bp,
                "legacy SN100x native HAL linkage changed: " + token)
    require('name: "se_nq_extn_client"' in base,
            "old SN100x eSE client module changed")
    require("vendor.nxp.hardware.nfc@2.0-service" in make
            and "nfc_nci.nqx.default.hw" in make,
            "legacy SN100x product package selection changed")
    for call in ("initializeEseClient();", "checkEseClientUpdate();",
                 "perform_eSEClientUpdate();"):
        require(call in startup,
                "old separate HAL-repo startup updater changed: " + call)
    svc2 = show(root, ref, "1.2/NxpNfcService.cpp")
    require("perform_eSEClientUpdate();" in svc2,
            "historical independent eSE updater evidence missing")
    print("PASS: separate 2022 SN100x library defines old HIDL/eSE client graph")
    print("PASS: eSE boot-update calls belong to DIFFERENT old repository startup")
    print("DECISION: no claim that the row173 wrapper invokes that updater")


def modern_sources(aosp, newer):
    official = pin(aosp, "refs/tags/android-17.0.0_r1",
                   OFF_SHA, OFF_TREE, "official AOSP17 NXP HAL")
    vendor = pin(newer, "refs/remotes/origin/br_ar_17_aosp_mainline",
                 NXP_SHA, NXP_TREE, "NXP 17.07.00 vendor source")
    off_bp = show(aosp, official, "snxxx/Android.bp")
    vendor_bp = show(newer, vendor, "snxxx/Android.bp")
    iface = show(aosp, official, "intf/nxpnfc/aidl/Android.bp")
    aidl = show(aosp, official,
                "intf/nxpnfc/aidl/vendor/nxp/nxpnfc_aidl/INxpNfc.aidl")
    vintf_off = ET.fromstring(show(
        aosp, official, "snxxx/aidl/2.0/nfc2-service-nxp.xml"))
    vintf_newer = ET.fromstring(show(
        newer, vendor, "snxxx/aidl/2.0/nfc2-service-nxp.xml"))
    require('name: "android.hardware.nfc-service.nxp"' in off_bp
            and 'name: "android.hardware.nfc2-service.nxp"' in off_bp,
            "official AOSP17 NFC native service choices changed")
    require('name: "android.hardware.nfc2-service.nxp"' in vendor_bp
            and '"android.hardware.nfc-V2-ndk"' in vendor_bp
            and '"vendor.nxp.nxpnfc_aidl-V1-ndk"' in vendor_bp,
            "newer NXP NFC native AIDL V2 service changed")
    require('name: "vendor.nxp.nxpnfc_aidl"' in iface
            and 'stability: "vintf"' in iface and "ndk: {" in iface,
            "official AOSP17 NFC vendor interface changed")
    for method in ("getVendorParam(", "setVendorParam(",
                   "resetEse(", "setNxpTransitConfig("):
        require(method in aidl,
                "official NXP vendor AIDL missing: " + method)
    desired = {
        ("android.hardware.nfc", "2", "INfc/default", "aidl"),
        ("vendor.nxp.nxpnfc_aidl", None, "INxpNfc/default", "aidl"),
    }
    for label, root in (("official AOSP17", vintf_off),
                        ("current NXP", vintf_newer)):
        interfaces = {
            (h.findtext("name"), h.findtext("version"),
             h.findtext("fqname"), h.attrib.get("format"))
            for h in root.findall("hal")
        }
        require(interfaces == desired,
                f"{label} NFC AIDL2/vendor AIDL1 VINTF changed")
    print("PASS: official AOSP17 ALREADY defines NFC AIDL V2 + vendor AIDL V1")
    print("PASS: modern NXP service carries same AIDL VINTF contract")
    print("DECISION: AOSP17 official owner sufficient; never add old HIDL")
    print("OPEN: actual mondrian vendor firmware/HAL selection and build")


def manifest(root):
    root = Path(root)
    entry = ET.parse(root / "default.xml").getroot()
    require(len(entry) == 1 and entry[0].tag == "include"
            and entry[0].get("name") == "aosp17_pe_p2_kernel_configs.xml",
            "default Android17 source selection changed")
    base = ET.parse(root / "aosp17_pe_bootstrap.xml").getroot()
    paths = {p.get("path"): p.get("name") for p in base.findall("project")}
    for path, name in (
        ("hardware/nxp/nfc", "platform/hardware/nxp/nfc"),
        ("packages/modules/Nfc", "platform/packages/modules/Nfc"),
        ("system/secure_element", "platform/system/secure_element"),
    ):
        require(paths.get(path) == name,
                f"official AOSP17 source owner replaced at {path}")
    require(OLD_PATH not in paths and OLD_REPO not in paths.values(),
            "archived SN100x HIDL wrapper activated")
    validator = (root / "tools/validate_aosp17_base_profiles.py").read_text()
    tests = (root / "tools/test_aosp17_manifest_entrypoint.py").read_text()
    require(f'if "{OLD_PATH}" in projects:' in validator
            and f'"{OLD_REPO}"' in validator,
            "row 173 HIDL checkout/name deny guard not installed")
    for test in ("test_archived_sn100x_hidl_service_cannot_enter_android17",
                 "test_archived_sn100x_hidl_cannot_replace_aosp17_nxp_hal"):
        require(f"def {test}(" in tests,
                "row 173 negative test not installed: " + test)
    subprocess.run(
        [sys.executable, str(root / "tools/validate_aosp17_base_profiles.py")],
        cwd=root, check=True)
    print("PASS: 25 reviewed source profiles, official NFC/SE and row173 guards")


def main():
    require(len(sys.argv) == 7,
            "Usage: checker OLD_SN_HIDL OLD_PN_HIDL OLD_SN_HAL AOSP_NXP "
            "CURRENT_NXP MANIFEST")
    paths = [Path(s).resolve() for s in sys.argv[1:]]
    require(all(p.is_dir() for p in paths), "source checkout missing")
    legacy_compare(paths[0], paths[1])
    old_hal_source(paths[2])
    modern_sources(paths[3], paths[4])
    manifest(paths[5])
    print("PASS: row173 pinned SN100x/PN5xx HIDL versus modern AOSP17 NFC")
    print("NOT TESTED: Soong, NFC APEX, installed HAL, CTS/VTS, eSE, mondrian")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, ET.ParseError,
            subprocess.CalledProcessError) as error:
        print("FAIL:", error, file=sys.stderr)
        sys.exit(1)
