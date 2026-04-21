import json
import pandas as pd
import logging
import GenericTransformers

def GetPostureAsCsv(jsonResults):
    device = jsonResults['data']['device']
    posture = device.get('posture') or {}
    rows = []

    property_checks = ['hardDriveEncryption', 'screenLockPasscode', 'firewall', 'biometric', 'antivirus']
    for check in property_checks:
        data = posture.get(check) or {}
        rows.append({'check': check, 'status': data.get('isSatisfied'), 'detail': str(data.get('detected'))})

    os_data = posture.get('osVersion') or {}
    rows.append({'check': 'osVersion', 'status': os_data.get('isSatisfied'), 'detail': os_data.get('version')})

    provider_checks = ['crowdstrike', 'jamf', 'kandji', 'inTune', 'sentinelOne', 'onePassword']
    for check in provider_checks:
        data = posture.get(check) or {}
        if data:
            detail = data.get('failureReason') or data.get('failureDetails') or data.get('expiredAt') or ''
            rows.append({'check': check, 'status': str(data.get('isVerified')), 'detail': detail})

    manual = posture.get('manualVerification') or {}
    if manual:
        rows.append({'check': 'manualVerification', 'status': str(manual.get('isVerified')), 'detail': manual.get('value') or ''})

    df = pd.DataFrame(rows, columns=['check', 'status', 'detail'])
    pd.set_option('display.max_rows', None)
    return df

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id','name','isTrusted','activeState']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'deviceUpdate',columns)

def GetBlockAsCsv(jsonResults):
    columns = ['ok','error','id','name','isTrusted','activeState']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'deviceBlock',columns)

def GetUnblockAsCsv(jsonResults):
    columns = ['ok','error','id','name','isTrusted','activeState']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'deviceUnblock',columns)

def GetArchiveAsCsv(jsonResults):
    columns = ['ok','error','id','name','isTrusted','activeState']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'deviceArchive',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','user.email','osVersion','hardwareModel','hostname','username','serialNumber','activeState',
    'clientVersion','manufacturerName']

    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'device',columns)

def GetListAsCsv(jsonResults):
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','user.email','osVersion','username','serialNumber','clientVersion','activeState']
    #columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','lastConnectedAt','osVersion','hardwareModel','hostname','username','serialNumber','activeState','clientVersion','manufacturerName']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetAddSerialAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serialNumbersCreate',columns)

def GetRemoveSerialAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serialNumbersDelete',columns)

def GetSNListAsCsv(jsonResults):
    columns = ['id', 'serialNumber','createdAt','matchedDevices']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)