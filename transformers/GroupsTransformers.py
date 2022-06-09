import json
import pandas as pd

#GroupColumns = ['GroupID', 'GroupName','CreatedAt','updatedAt','isActive','Type','UserIdList','ResourceIdList']
GroupColumns = ['GroupID', 'GroupName','isActive','Type','UserIdList','ResourceIdList']

def ProcessOneItem(item):
    ItemId = item['id']
    ItemName = item['name']
    #createdAt = item['createdAt']
    #updatedAt = item['updatedAt']
    isActive = item['isActive']
    type = item['type']

    users = item['users']['edges']
    userIdList = []
    for userInList in users:
        user = userInList['node']
        userId = user['id']
        userIdList.append(userId)

    resourceIdList = []
    resources = item['resources']['edges']
    for resourceInList in resources:
        resource = resourceInList['node']
        resourceId = resource['id']
        resourceIdList.append(resourceId)

    #return [ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceIdList]
    return [ItemId,ItemName,isActive,type,userIdList,resourceIdList]

def GetAddOrRemoveResourcesAsCsv(jsonResults,objectname):
    GroupColumns = ['APIResponseOK','APIResponseError','GroupID', 'GroupName','ResourceIdList']
    data = []
    ApiResOK = jsonResults['data'][objectname]['ok']
    ApiResErr = jsonResults['data'][objectname]['error']
    item = jsonResults['data'][objectname]['entity']
    ItemId = item['id']
    ItemName = item['name']
    resources = item['resources']['edges']
    resIdList = []
    for resInList in resources:
        res = resInList['node']
        resId = res['id']
        resIdList.append(resId)

    data.append([ApiResOK,ApiResErr,ItemId,ItemName,resIdList])

    df = pd.DataFrame(data, columns = GroupColumns)

    #data.append([ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceIdList])
    return df

def GetAddOrRemoveUsersAsCsv(jsonResults,objectname):
    GroupColumns = ['APIResponseOK','APIResponseError','GroupID', 'GroupName','UserIdList']
    data = []
    ApiResOK = jsonResults['data'][objectname]['ok']
    ApiResErr = jsonResults['data'][objectname]['error']
    item = jsonResults['data'][objectname]['entity']
    ItemId = item['id']
    ItemName = item['name']
    users = item['users']['edges']
    userIdList = []
    for userInList in users:
        user = userInList['node']
        userId = user['id']
        userIdList.append(userId)

    data.append([ApiResOK,ApiResErr,ItemId,ItemName,userIdList])

    df = pd.DataFrame(data, columns = GroupColumns)

    #data.append([ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceIdList])
    return df

def GetCreateAsCsv(jsonResults,objectname):
    #GroupColumns = ['APIResponseOK','APIResponseError','GroupID', 'GroupName','isActive','Type','UserIdList','ResourceIdList']
    GroupColumns = ['APIResponseOK','APIResponseError','GroupID', 'GroupName','CreatedAt','updatedAt','isActive','Type','UserIdList','ResourceIdList']
    data = []
    ApiResOK = jsonResults['data'][objectname]['ok']
    ApiResErr = jsonResults['data'][objectname]['error']
    item = jsonResults['data'][objectname]['entity']
    ItemId = item['id']
    ItemName = item['name']
    #createdAt = item['createdAt']
    #updatedAt = item['updatedAt']
    isActive = item['isActive']
    type = item['type']

    users = item['users']['edges']
    userIdList = []
    for userInList in users:
        user = userInList['node']
        userId = user['id']
        userIdList.append(userId)

    resourceIdList = []
    resources = item['resources']['edges']
    for resourceInList in resources:
        resource = resourceInList['node']
        resourceId = resource['id']
        resourceIdList.append(resourceId)

    #data.append([ApiResOK,ApiResErr,ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceIdList])
    data.append([ApiResOK,ApiResErr,ItemId,ItemName,isActive,type,userIdList,resourceIdList])
    df = pd.DataFrame(data,columns = GroupColumns)

    return df

def GetShowAsCsv(jsonResults,objectname):
    data = []
    item = jsonResults['data'][objectname]
    if item is not None:
        data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = GroupColumns)

    #data.append([ItemId,ItemName,createdAt,updatedAt,isActive,type,userIdList,resourceIdList])
    return df

def GetListAsCsv(jsonResults,objectname):

    data = []

    ItemList = jsonResults['data'][objectname]['edges']
    for itemInList in ItemList:
        item = itemInList['node']
        data.append(ProcessOneItem(item))

    df = pd.DataFrame(data, columns = GroupColumns)
    #dfItem = pd.json_normalize(DeviceList)
    return df
