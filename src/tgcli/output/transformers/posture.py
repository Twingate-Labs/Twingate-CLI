"""Device posture data transformers."""

from __future__ import annotations

import pandas as pd


def _prop(node: dict | None, detail_key: str):
    """Flatten a DevicePropertyPostureCheck or OsVersionPostureCheck."""
    if node is None:
        return None, None
    return node.get("isSatisfied"), node.get(detail_key)


def _trust(node: dict | None):
    """Flatten a TrustProviderVerification."""
    if node is None:
        return None, None, None, None
    return (
        node.get("isVerified"),
        node.get("failureReason"),
        node.get("expiredAt"),
        node.get("failureDetails"),
    )


def get_device_posture_as_csv(json_results: dict) -> pd.DataFrame:
    posture = json_results["data"]["devicePosture"]

    hde_sat, hde_det = _prop(posture.get("hardDriveEncryption"), "detected")
    slp_sat, slp_det = _prop(posture.get("screenLockPasscode"), "detected")
    fw_sat,  fw_det  = _prop(posture.get("firewall"), "detected")
    bio_sat, bio_det = _prop(posture.get("biometric"), "detected")
    av_sat,  av_det  = _prop(posture.get("antivirus"), "detected")
    os_sat,  os_ver  = _prop(posture.get("osVersion"), "version")

    cs_ver, cs_fr, cs_exp, cs_fd = _trust(posture.get("crowdstrike"))
    jf_ver, jf_fr, jf_exp, jf_fd = _trust(posture.get("jamf"))
    kd_ver, kd_fr, kd_exp, kd_fd = _trust(posture.get("kandji"))
    it_ver, it_fr, it_exp, it_fd = _trust(posture.get("inTune"))
    s1_ver, s1_fr, s1_exp, s1_fd = _trust(posture.get("sentinelOne"))
    op_ver, op_fr, op_exp, op_fd = _trust(posture.get("onePassword"))

    mv = posture.get("manualVerification")
    mv_ver = mv.get("isVerified") if mv else None
    mv_val = mv.get("value") if mv else None

    columns = [
        "hardDriveEncryption.isSatisfied", "hardDriveEncryption.detected",
        "screenLockPasscode.isSatisfied",  "screenLockPasscode.detected",
        "firewall.isSatisfied",            "firewall.detected",
        "biometric.isSatisfied",           "biometric.detected",
        "antivirus.isSatisfied",           "antivirus.detected",
        "osVersion.isSatisfied",           "osVersion.version",
        "crowdstrike.isVerified",  "crowdstrike.failureReason",  "crowdstrike.expiredAt",  "crowdstrike.failureDetails",
        "jamf.isVerified",         "jamf.failureReason",         "jamf.expiredAt",         "jamf.failureDetails",
        "kandji.isVerified",       "kandji.failureReason",       "kandji.expiredAt",       "kandji.failureDetails",
        "inTune.isVerified",       "inTune.failureReason",       "inTune.expiredAt",       "inTune.failureDetails",
        "sentinelOne.isVerified",  "sentinelOne.failureReason",  "sentinelOne.expiredAt",  "sentinelOne.failureDetails",
        "onePassword.isVerified",  "onePassword.failureReason",  "onePassword.expiredAt",  "onePassword.failureDetails",
        "manualVerification.isVerified", "manualVerification.value",
    ]

    data = [[
        hde_sat, hde_det,
        slp_sat, slp_det,
        fw_sat,  fw_det,
        bio_sat, bio_det,
        av_sat,  av_det,
        os_sat,  os_ver,
        cs_ver, cs_fr, cs_exp, cs_fd,
        jf_ver, jf_fr, jf_exp, jf_fd,
        kd_ver, kd_fr, kd_exp, kd_fd,
        it_ver, it_fr, it_exp, it_fd,
        s1_ver, s1_fr, s1_exp, s1_fd,
        op_ver, op_fr, op_exp, op_fd,
        mv_ver, mv_val,
    ]]

    pd.set_option("display.max_rows", None)
    return pd.DataFrame(data, columns=columns)
