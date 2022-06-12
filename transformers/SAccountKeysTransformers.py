import json
import pandas as pd
import logging

#AccountColumns = ['AccountID', 'AccountName','CreatedAt','updatedAt','KeyIdList']
AccountColumns = ['ItemID', 'ItemName','expiresAt','revokedAt','status','serviceAccountId']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    #createdAt = item['createdAt']
    #updatedAt = item['updatedAt']
    expiresAt = item['expiresAt']
    revokedAt = item['revokedAt']
    status = item['status']
    saname = item['serviceAccount']['name']
    said = item['serviceAccount']['id']
    #return [ItemId,ItemName,createdAt,updatedAt,keyIdList]
    return [ItemId,ItemName,expiresAt,revokedAt,status,said]

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    data.append(ProcessOneItem(item))
    df = pd.DataFrame(data, columns = AccountColumns)
    return df


def GetCreateAsCsv(jsonResults,objectname):
    #GroupColumns = ['APIResponseOK','APIResponseError','GroupID', 'GroupName','isActive','Type','UserIdList','ResourceIdList']
    GroupColumns = ['APIResponseOK','APIResponseError','Token', 'ItemId','ItemName','expiresAt','createdAt']
    data = []

    ApiResOK = jsonResults['data'][objectname]['ok']
    ApiResErr = jsonResults['data'][objectname]['error']
    if not ApiResErr:
        Token = jsonResults['data'][objectname]['token']
        item = jsonResults['data'][objectname]['entity']
        ItemId = item['id']
        ItemName = item['name']
        createdAt = item['createdAt']
        expiresAt = item['expiresAt']
        data.append([ApiResOK,ApiResErr,Token,ItemId,ItemName,expiresAt,createdAt])
    else:
        data.append([ApiResOK,ApiResErr,None,None,None,None,None])
    df = pd.DataFrame(data,columns = GroupColumns)

    return df