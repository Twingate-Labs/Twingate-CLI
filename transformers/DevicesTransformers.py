import json
import pandas as pd
import logging
import GenericTransformers

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
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','user.email','osVersion','username','serialNumber','clientVersion']
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