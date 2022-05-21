import json
import pandas as pd

def GetListAsCsv(jsonResults,ObjectName):

    GenList = jsonResults['data'][ObjectName]['edges']
    dfItem = pd.json_normalize(GenList)
    return dfItem

def GetShowAsCsv(jsonResults,ObjectName):

    GenList = jsonResults['data'][ObjectName]
    dfItem = pd.json_normalize(GenList)
    return dfItem

def GetCreateAsCsv(jsonResults,objectname):
    #{'data': {'resourceCreate': {'ok': True, 'error': None, 'entity': {'id': 'UmVzb3VyY2U6MjE2OTgxNA==', 'name': 'MyDevice1'}}}}
    item = jsonResults['data'][objectname]
    IsOk = item['ok']
    IsError = item['error']
    ent = item['entity']
    id = ent['id']
    name = ent['name']
    data = [[IsOk,IsError,id,name]]
    df = pd.DataFrame(data, columns = ['APIResponseOK', 'APIResponseError','ItemID','ItemName'])
    return df

def GetDeleteAsCsv(jsonResults,objectname):
    #{'data': {'resourceCreate': {'ok': True, 'error': None, 'entity': {'id': 'UmVzb3VyY2U6MjE2OTgxNA==', 'name': 'MyDevice1'}}}}
    item = jsonResults['data'][objectname]
    IsOk = item['ok']
    IsError = item['error']
    data = [[IsOk,IsError]]
    df = pd.DataFrame(data, columns = ['APIResponseOK', 'APIResponseError'])
    return df
