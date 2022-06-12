import json
import pandas as pd
import logging

#AccountColumns = ['AccountID', 'AccountName','CreatedAt','updatedAt','KeyIdList']
AccountColumns = ['AccountID', 'AccountName','KeyIdList','ResIdList']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    #createdAt = item['createdAt']
    #updatedAt = item['updatedAt']

    keys = item['keys']['edges']
    keyIdList = []
    for keyInList in keys:
        key = keyInList['node']
        keyId = key['id']
        keyIdList.append(keyId)

    resources = item['resources']['edges']
    resourceIdList = []
    for resInList in resources:
        res = resInList['node']
        resId = res['id']
        resourceIdList.append(resId)

    #return [ItemId,ItemName,createdAt,updatedAt,keyIdList]
    return [ItemId,ItemName,keyIdList,resourceIdList]

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    if item is not None:
        data.append(ProcessOneItem(item))
    else:
        data=[[None,None,None,None]]
    df = pd.DataFrame(data, columns = AccountColumns)
    return df

def GetListAsCsv(jsonResults,objectname):
    data = []
    ItemList = jsonResults['data'][objectname]['edges']
    for itemInList in ItemList:
        item = itemInList['node']
        data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = AccountColumns)
    return df
