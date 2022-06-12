import json
import pandas as pd
import logging
import GenericTransformers

def GetUpdateAsCsv(jsonResults):
    
    columns = ['ok','error','id','name','isTrusted']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'deviceUpdate',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','osVersion','lastSuccessfulLoginAt','hardwareModel','hostname','username','serialNumber',
    'clientVersion','manufacturerName']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'device',columns)

def GetListAsCsv(jsonResults):
    columns = ['id', 'name','isTrusted','osName','deviceType','lastFailedLoginAt','osVersion','lastSuccessfulLoginAt','hardwareModel','hostname','username','serialNumber',
    'clientVersion','manufacturerName']
    return GenericTransformers.GetListAsCsvNoNesting(jsonResults,'devices',columns)