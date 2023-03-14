import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import DevicesTransformers
import StdResponses
import StdAPIUtils

def get_device_archive_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"deviceID":JsonData['itemid']}

    Body = """
    mutation
        updateDevice($deviceID: ID!){
            deviceArchive(id: $deviceID) {
                ok
                error
                entity {
                    id
                    name
                    isTrusted
                    activeState
                }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_device_unblock_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"deviceID":JsonData['itemid']}

    Body = """
    mutation
        updateDevice($deviceID: ID!){
            deviceUnblock(id: $deviceID) {
                ok
                error
                entity {
                    id
                    name
                    isTrusted
                    activeState
                }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_device_block_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"deviceID":JsonData['itemid']}

    Body = """
    mutation
        updateDevice($deviceID: ID!){
            deviceBlock(id: $deviceID) {
                ok
                error
                entity {
                    id
                    name
                    isTrusted
                    activeState
                }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_device_update_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    #print("Debug:"+JsonData['deviceid'])
# Modify True to False if you wish to untrust a device as opposed to trust it
    variables = {"deviceID":JsonData['itemid'] ,"isTrusted":JsonData['trust']}

    Body = """
    mutation
        updateDeviceTrust($deviceID: ID!, $isTrusted: Boolean!){
            deviceUpdate(id: $deviceID, isTrusted: $isTrusted) {
                ok
                error
                entity {
                    id
                    name
                    isTrusted

                }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables


def get_device_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
    query listGroup($cursor: String!)
    {
          devices(after: $cursor, first:null) {
                pageInfo {
                    endCursor
                    hasNextPage
                }
            edges {
              node {
                id
                name
                isTrusted
                osName
                deviceType
                lastFailedLoginAt
                lastSuccessfulLoginAt
                osVersion
                hardwareModel
                hostname
                username
                serialNumber
                user{
                    firstName
                    lastName
                    email
                }
                lastConnectedAt
                osName
                deviceType
                activeState
                clientVersion
                manufacturerName
              }
            }
          }
        }"""

    return True,api_call_type,Headers,Body,variables

def get_device_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"deviceID":JsonData['itemid']}
    Body = """
         query
            getDevice($deviceID: ID!){
          device(id:$deviceID) {
            id
            name
            isTrusted
            osName
            deviceType
            lastFailedLoginAt
            lastSuccessfulLoginAt
            osVersion
            hardwareModel
            hostname
            username
            serialNumber
            lastConnectedAt
            osName
            deviceType
            activeState
            clientVersion
            manufacturerName
              }
          }
    """

    return True,api_call_type,Headers,Body,variables


def item_list(outputFormat,sessionname,idsfile,idsonly):
    #r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_list_resources,{},DevicesTransformers.GetListAsCsv)
    #if idsonly:
    #    j = GenericTransformers.GetIds(j,"devices")
    #    print(j)
    #    exit(0)
    #else:
    #    if idsfile != "":
    #        itemsAdded,itemsRemoved = GenericTransformers.GetIdsAndCompareToFile(j,idsfile,"devices")
    #        print({'itemsAddedCount':len(list(itemsAdded)),'itemsAdded':list(itemsAdded),'itemsRemovedCount':len(list(itemsRemoved)),'itemsRemoved':list(itemsRemoved)})
    #    else:
    #        print(r)
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_list_resources,{'cursor':Cursor},DevicesTransformers.GetListAsCsv)
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'devices')
        #print("DEBUG: Has More pages:"+str(hasMorePages))
        ListOfResponses.append(j['data']['devices']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,DevicesTransformers.GetListAsCsv)
    print(output)

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_show_resources,{'itemid':itemid},DevicesTransformers.GetShowAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetShowAsCsv)
    print(output)

def item_update(outputFormat,sessionname,itemid,trust):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_update_resources,{'itemid':itemid,'trust':trust},DevicesTransformers.GetUpdateAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetUpdateAsCsv)
    print(output)

def item_block(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_block_resources,{'itemid':itemid},DevicesTransformers.GetBlockAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetBlockAsCsv)
    print(output)

def item_unblock(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_unblock_resources,{'itemid':itemid},DevicesTransformers.GetUnblockAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetUnblockAsCsv)
    print(output)

def item_archive(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_device_archive_resources,{'itemid':itemid},DevicesTransformers.GetArchiveAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetArchiveAsCsv)
    print(output)