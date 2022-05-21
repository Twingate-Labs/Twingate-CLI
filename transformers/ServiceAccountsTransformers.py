import json
import pandas as pd

AccountColumns = ['AccountID', 'AccountName','CreatedAt','updatedAt','KeyIdList']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    createdAt = item['createdAt']
    updatedAt = item['updatedAt']

    keys = item['keys']['edges']
    keyIdList = []
    for keyInList in keys:
        key = keyInList['node']
        keyId = key['id']
        keyIdList.append(keyId)

    return [ItemId,ItemName,createdAt,updatedAt,keyIdList]

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    data.append(ProcessOneItem(item))
    df = pd.DataFrame(data, columns = AccountColumns)
    return df

def GetListAsCsv(jsonResults,objectname):

    data = []
    ItemList = jsonResults['data'][objectname]['edges']
    for itemInList in ItemList:
        item = itemInList['node']
        data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = AccountColumns)
    #dfItem = pd.json_normalize(DeviceList)
    return df
