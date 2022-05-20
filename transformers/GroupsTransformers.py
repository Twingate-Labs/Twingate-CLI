import json
import pandas as pd

def GetListAsCsv(jsonResults,objectname):

    data = []
    ItemList = jsonResults['data'][objectname]['edges']
    for itemInList in ItemList:
        item = itemInList['node']
        ItemId = item['id']
        ItemName = item['name']
        createdAt = item['createdAt']
        updatedAt = item['updatedAt']
        isActive = item['isActive']
        type = item['type']

        users = item['users']['edges']
        userIdList = []
        for userInList in users:
            user = userInList['node']
            userId = user['id']
            userIdList.append(userId)
            #email = user['email']
            #firstName = user['firstName']
            #lastName = user['lastName']
        resourceIdList = []
        resources = item['resources']['edges']
        for resourceInList in resources:
            resource = resourceInList['node']
            resourceId = resource['id']
            resourceIdList.append(resourceId)

        data.append([ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceId])

    df = pd.DataFrame(data, columns = ['GroupID', 'GroupName','CreatedAt','updatedAt','isActive','Type','UserIdList','ResourceIdList'])
    #dfItem = pd.json_normalize(DeviceList)
    return df
