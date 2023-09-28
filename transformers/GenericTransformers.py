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
                #print("col:"+col)
                #Info = item['entity'][col]
                if '.' in col:
                    PathToInfo = col.split(".")
                    #print(PathToInfo)
                    logging.debug("path to info:" + str(PathToInfo))
                    Info = item['entity'][PathToInfo[0]][PathToInfo[1]]
                else:
                    logging.debug("entity:" + str(item['entity']))
                    logging.debug("entity:" + str(col))
                    Info = item['entity'][col]

                #print(Info)
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
    if datarow[0] == False:
        emptydatarow = [None] * len(columns)
        emptydatarow[0] = datarow[0]
        emptydatarow[1] = datarow[1]
        data = [emptydatarow]
    df = pd.DataFrame(data, columns = columns)
    pd.set_option('display.max_rows', None)
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
    pd.set_option('display.max_rows', None)
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
    pd.set_option('display.max_rows', None)
    return df


def GetListAsCsv(jsonResults,columns):
    AllLists = jsonResults
    data = []
    #print(str(AllLists))
    for GenList in AllLists:
        for item in GenList:
            #print("ITEM: "+str(item))
            datarow = []
            for col in columns:
                if item['node'] is not None:
                    if '.' in col:
                        PathToInfo = col.split(".")
                        logging.debug("path to info:" + str(PathToInfo))
                        logging.debug("item:" + str(item['node']))
                        l1_item = item['node'][PathToInfo[0]]
                        if l1_item != None:
                            content = item['node'][PathToInfo[0]][PathToInfo[1]]
                        else:
                            content = item['node'][PathToInfo[0]]
                            logging.debug("Oops - looks like I couldnt find attribute " +str(PathToInfo[1])+" in " +str(item['node']))
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
    pd.set_option('display.max_rows', None)
    return df

def CheckIfMorePages(jsonResults,objName):
    pInfo = jsonResults['data'][objName]['pageInfo']
    hasNextPage = pInfo['hasNextPage']
    if hasNextPage:
        Cursor = pInfo['endCursor']
        return True,Cursor
    else:
        return False,None

