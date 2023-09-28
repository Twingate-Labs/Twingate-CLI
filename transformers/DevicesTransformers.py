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
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','lastConnectedAt','osVersion','hardwareModel','hostname','username','serialNumber','activeState',
    'clientVersion','manufacturerName']

    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'device',columns)

def GetListAsCsv(jsonResults):
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','lastConnectedAt','osVersion','username','serialNumber','clientVersion']
    #columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','lastSuccessfulLoginAt','lastConnectedAt','osVersion','hardwareModel','hostname','username','serialNumber','activeState','clientVersion','manufacturerName']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)