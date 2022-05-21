import json
import pandas as pd

NetworkColumns = ['GroupID', 'GroupName','CreatedAt','updatedAt','isActive','connectorIdList','ResourceIdList']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    createdAt = item['createdAt']
    updatedAt = item['updatedAt']
    isActive = item['isActive']

    connectors = item['connectors']['edges']
    connectorIdList = []
    for connectorInList in connectors:
        connector = connectorInList['node']
        connectorId = connector['id']
        connectorIdList.append(connectorId)

    resourceIdList = []
    resources = item['resources']['edges']
    for resourceInList in resources:
        resource = resourceInList['node']
        resourceId = resource['id']
        resourceIdList.append(resourceId)

    return [ItemId,ItemName,createdAt,updatedAt,isActive,connectorIdList,resourceIdList]

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = NetworkColumns)

    return df

def GetListAsCsv(jsonResults,objectname):

    data = []
    ItemList = jsonResults['data'][objectname]['edges']
    for itemInList in ItemList:
        item = itemInList['node']
        data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = NetworkColumns)
    #dfItem = pd.json_normalize(DeviceList)
    return df
