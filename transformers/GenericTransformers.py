import json
import os
import pandas as pd
import logging

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

def GetUpdateAsCsvNoNesting(jsonResults,objectname,columns):
    item = jsonResults['data'][objectname]
    datarow = []
    IsOk = item[columns[0]]
    datarow.append(IsOk)
    IsError = item[columns[1]]
    IsError = datarow.append(IsError)

    for col in columns[2:]:
        if IsOk:
            if not col == "token":
                Info = item['entity'][col]
                if str(Info).startswith('{\'edges\':'):
                    IDs = []
                    for el in Info['edges']:
                        IDs.append(el['node']['id'])
                    Info = IDs
                datarow.append(Info)

        else:
            datarow.append(None)
    
    if 'token' in columns:
        token = item['token']
        datarow.append(token)
    data = [datarow]
    
    df = pd.DataFrame(data, columns = columns)
    return df

def GetShowAsCsvNoNesting(jsonResults,objectname,columns):
    item = jsonResults['data'][objectname]
    datarow = []
    for col in columns:
        if item is not None:
            if '.' in col:
                PathToInfo = col.split(".")
                Info = item[PathToInfo[0]][PathToInfo[1]]
            else:
                Info = item[col]
        
            if str(Info).startswith('{\'edges\':'):
                IDs = []
                for el in Info['edges']:
                    IDs.append(el['node']['id'])
                Info = IDs
            datarow.append(Info)
        else:
           datarow.append(None) 
    data = [datarow]

    df = pd.DataFrame(data, columns = columns)
    return df

def GetListAsCsvNoNesting(jsonResults,ObjectName,columns):
    GenList = jsonResults['data'][ObjectName]['edges']
    data = []
    for item in GenList:
        datarow = []
        for col in columns:
            if item['node'] is not None:
                if '.' in col:
                    PathToInfo = col.split(".")
                    content = item['node'][PathToInfo[0]][PathToInfo[1]]
                else:
                    content = item['node'][col]

                if str(content).startswith('{\'edges\':'):
                    IDs = []
                    for el in content['edges']:
                        IDs.append(el['node']['id'])
                    content = IDs
                datarow.append(content)
            else:
                datarow.append(None) 
        data.append(datarow)

    df = pd.DataFrame(data, columns = columns)
    return df