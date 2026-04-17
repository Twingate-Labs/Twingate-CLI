import json
import pandas as pd
import logging
import GenericTransformers


def GetListAsCsv(jsonResults):
    columns = ['id', 'name', 'description', 'type', 'action', 'status', 'createdAt', 'updatedAt']
    return GenericTransformers.GetListAsCsv(jsonResults, columns)


def GetShowAsCsv(jsonResults):
    columns = ['id', 'name', 'description', 'type', 'action', 'status', 'createdAt', 'updatedAt']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults, 'devicePostureCheck', columns)


def GetCreateAsCsv(jsonResults):
    columns = ['ok', 'error', 'id', 'name', 'description', 'type', 'action', 'status']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckCreate', columns)


def GetUpdateAsCsv(jsonResults):
    columns = ['ok', 'error', 'id', 'name', 'description', 'type', 'action', 'status']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckUpdate', columns)


def GetDeleteAsCsv(jsonResults):
    columns = ['ok', 'error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckDelete', columns)


def GetDevicePostureAsCsv(jsonResults):
    posture = jsonResults['data']['devicePosture']

    def prop(field):
        """Flatten a DevicePropertyPostureCheck or OsVersionPostureCheck."""
        if posture.get(field) is None:
            return None, None
        node = posture[field]
        satisfied = node.get('isSatisfied')
        # DevicePropertyPostureCheck has 'detected'; OsVersionPostureCheck has 'version'
        detail = node.get('detected') if 'detected' in node else node.get('version')
        return satisfied, detail

    def trust(field):
        """Flatten a TrustProviderVerification."""
        if posture.get(field) is None:
            return None, None, None, None
        node = posture[field]
        return (
            node.get('isVerified'),
            node.get('failureReason'),
            node.get('expiredAt'),
            node.get('failureDetails'),
        )

    def manual():
        if posture.get('manualVerification') is None:
            return None, None
        node = posture['manualVerification']
        return node.get('isVerified'), node.get('value')

    hde_sat, hde_det   = prop('hardDriveEncryption')
    slp_sat, slp_det   = prop('screenLockPasscode')
    fw_sat,  fw_det    = prop('firewall')
    bio_sat, bio_det   = prop('biometric')
    av_sat,  av_det    = prop('antivirus')
    os_sat,  os_ver    = prop('osVersion')
    cs_ver,  cs_fr, cs_exp, cs_fd  = trust('crowdstrike')
    jf_ver,  jf_fr, jf_exp, jf_fd  = trust('jamf')
    kd_ver,  kd_fr, kd_exp, kd_fd  = trust('kandji')
    it_ver,  it_fr, it_exp, it_fd  = trust('inTune')
    s1_ver,  s1_fr, s1_exp, s1_fd  = trust('sentinelOne')
    op_ver,  op_fr, op_exp, op_fd  = trust('onePassword')
    mv_ver,  mv_val                = manual()

    columns = [
        'hardDriveEncryption.isSatisfied', 'hardDriveEncryption.detected',
        'screenLockPasscode.isSatisfied',  'screenLockPasscode.detected',
        'firewall.isSatisfied',            'firewall.detected',
        'biometric.isSatisfied',           'biometric.detected',
        'antivirus.isSatisfied',           'antivirus.detected',
        'osVersion.isSatisfied',           'osVersion.version',
        'crowdstrike.isVerified',   'crowdstrike.failureReason',   'crowdstrike.expiredAt',   'crowdstrike.failureDetails',
        'jamf.isVerified',          'jamf.failureReason',          'jamf.expiredAt',          'jamf.failureDetails',
        'kandji.isVerified',        'kandji.failureReason',        'kandji.expiredAt',        'kandji.failureDetails',
        'inTune.isVerified',        'inTune.failureReason',        'inTune.expiredAt',        'inTune.failureDetails',
        'sentinelOne.isVerified',   'sentinelOne.failureReason',   'sentinelOne.expiredAt',   'sentinelOne.failureDetails',
        'onePassword.isVerified',   'onePassword.failureReason',   'onePassword.expiredAt',   'onePassword.failureDetails',
        'manualVerification.isVerified', 'manualVerification.value',
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

    df = pd.DataFrame(data, columns=columns)
    pd.set_option('display.max_rows', None)
    return df
