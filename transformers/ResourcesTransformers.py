import json
import pandas as pd
import logging

def GetUpdateAsCsv(jsonResults,objectname):
    # {"data":{"deviceUpdate":{"ok":true,"error":null,"entity":{"id":"RGV2aWNlOjE5MzI2OQ==","name":"DESKTOP-FFPADSA","isTrusted":true}}}}
    IsOk = jsonResults['data']['deviceUpdate']['ok']
    IsError = jsonResults['data']['deviceUpdate']['error']
    EntityID = jsonResults['data']['deviceUpdate']['entity']['id']
    EntityName = jsonResults['data']['deviceUpdate']['entity']['name']
    EntityIsTrusted = jsonResults['data']['deviceUpdate']['entity']['isTrusted']
    data = [[IsOk,IsError,EntityID,EntityName,EntityIsTrusted]]
    df = pd.DataFrame(data, columns = ['APIResponseOK', 'APIResponseError','DeviceID','DeviceName','isTrusted'])
    return df

def GetShowAsCsv(jsonResults,objectname):

    item = jsonResults['data']
    dfItem = pd.json_normalize(item)
    return dfItem
