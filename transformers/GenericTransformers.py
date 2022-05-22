import json
import os
import pandas as pd

def GetIds(jsonResults,ObjectName):
    IDs = []
    GenList = jsonResults['data'][ObjectName]['edges']
    for item in GenList:
        id = item['node']['id']
        IDs.append(id)
    return IDs

def GetIdsAndCompareToFile(jsonResults,idsfile,ObjectName):
    IDs = GetIds(jsonResults,ObjectName)
    #print(IDs)
    with open(idsfile) as f:
        contents = f.read()
        IdsFromFileAsList = contents.replace('[','').replace(']','').replace('\'','').replace('\n','').replace(' ','').split(",")

    ItemsAdded = set(IDs) - set(IdsFromFileAsList)
    ItemsRemoved = set(IdsFromFileAsList) - set(IDs)

    return ItemsAdded,ItemsRemoved

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
