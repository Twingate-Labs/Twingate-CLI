import json
import pandas as pd
import logging

#NetworkColumns = ['GroupID', 'GroupName','CreatedAt','updatedAt','isActive','connectorIdList','ResourceIdList']
NetworkColumns = ['GroupID', 'GroupName','isActive','connectorIdList','ResourceIdList']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    #createdAt = item['createdAt']
    #updatedAt = item['updatedAt']
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

    #return [ItemId,ItemName,createdAt,updatedAt,isActive,connectorIdList,resourceIdList]
    return [ItemId,ItemName,isActive,connectorIdList,resourceIdList]

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = NetworkColumns)

    return df