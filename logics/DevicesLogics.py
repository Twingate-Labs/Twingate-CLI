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


def get_serialnum_list_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}


    Body = """
     query PM_GetListOfSerialNumbers($cursor: String!)
    {
    serialNumbers(after: $cursor) {
        edges {
        node {
            id
            serialNumber
            createdAt
            matchedDevices {
                id
                name
            }
        }
        }
        pageInfo {
        endCursor
        hasNextPage
        }
    }
    }
    """
    return True,api_call_type,Headers,Body,variables

def get_serialnum_add_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"serialnums":JsonData['serialnums']}

    Body = """
        mutation PM_serialNumbersCreate($serialnums: [String!]!) {

            serialNumbersCreate(serialNumbers: $serialnums) {
            ok
            error
            entities {
                id
                createdAt
                serialNumber
                matchedDevices {
                    id
                    name
                }
            }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_serialnum_delete_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"serialnums":JsonData['serialnums']}

    Body = """
        mutation PM_serialNumbersDelete($serialnums: [String!]!) {

            serialNumbersDelete(serialNumbers: $serialnums) {
            ok
            error
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_device_archive_resources(token,JsonData):
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

def get_device_unblock_resources(token,JsonData):
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

def get_device_block_resources(token,JsonData):
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

def get_device_update_resources(token,JsonData):
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
                    activeState

                }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables


def get_device_list_resources(token,JsonData):
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
                lastConnectedAt
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

def get_device_show_resources(token,JsonData):
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
            lastConnectedAt
            osVersion
            hardwareModel
            hostname
            username
            serialNumber
            
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
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'devices')
        #print("DEBUG: Has More pages:"+str(hasMorePages))
        ListOfResponses.append(j['data']['devices']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,DevicesTransformers.GetListAsCsv)
    print(output)

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_show_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetShowAsCsv)
    print(output)

def item_update(outputFormat,sessionname,itemid,trust):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_update_resources,{'itemid':itemid,'trust':trust})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetUpdateAsCsv)
    print(output)

def item_block(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_block_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetBlockAsCsv)
    print(output)

def item_unblock(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_unblock_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetUnblockAsCsv)
    print(output)

def item_archive(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_device_archive_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetArchiveAsCsv)
    print(output)

def add_serialnumbers(outputFormat,sessionname,serialnums):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_serialnum_add_resources,{'serialnums':serialnums})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetAddSerialAsCsv)
    print(output)

def remove_serialnumbers(outputFormat,sessionname,serialnums):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_serialnum_delete_resources,{'serialnums':serialnums})
    output,r = StdAPIUtils.format_output(j,outputFormat,DevicesTransformers.GetRemoveSerialAsCsv)
    print(output)

def snumber_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_serialnum_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'serialNumbers')
        #print("DEBUG: Has More pages:"+str(hasMorePages))
        ListOfResponses.append(j['data']['serialNumbers']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,DevicesTransformers.GetSNListAsCsv)
    print(output)