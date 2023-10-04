import json
import pandas as pd
import logging
import GenericTransformers

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

def GetShowAsCsv(jsonResults):
    columns = ['id','name','isActive','remoteNetwork.id','address.type','address.value','protocols.allowIcmp',
    'protocols.tcp.policy','protocols.udp.policy','isVisible','isBrowserShortcutEnabled']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'resource',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','name','isActive','remoteNetwork.id','address.type','address.value','access.edges','securityPolicy.id','alias','isVisible','isBrowserShortcutEnabled']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceCreate',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceDelete',columns)

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','remoteNetwork.id','remoteNetwork.name','address.type','address.value','alias']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceUpdate',columns)

def GetVisibilityUpdateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','isVisible','isBrowserShortcutEnabled']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceUpdate',columns)