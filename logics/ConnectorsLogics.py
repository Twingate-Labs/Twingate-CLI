import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import ConnectorsTransformers
import GenericTransformers
import StdResponses
import StdAPIUtils

def get_connector_rename_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid'],'name':JsonData['itemname']}
    Body = """
        mutation
            ObjRename($id:ID!,$name:String!){
            connectorUpdate(id: $id, name: $name) {
            ok
            error
            entity{
              id
              name
            }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_connector_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
        query listObj($cursor: String!)
        {
          connectors(after: $cursor, first:null) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                id
                name
                state
                lastHeartbeatAt
                createdAt
                updatedAt
              }
            }
          }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_connector_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
        query
        getObj($itemID: ID!){
      connector(id:$itemID) {
            id
            name
            state
            lastHeartbeatAt
            remoteNetwork{
                id
                name
            }
          }
      }
    """

    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_show_resources,{'itemid':itemid},ConnectorsTransformers.GetShowAsCsv)
    #print(r)
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetShowAsCsv)
    print(output)

def item_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_list_resources,{'cursor':Cursor},ConnectorsTransformers.GetListAsCsv)
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'connectors')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['connectors']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,ConnectorsTransformers.GetListAsCsv)
    print(output)


def item_rename(outputFormat,sessionname,itemid,itemname):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_rename_resources,{'itemid':itemid,'itemname':itemname},ConnectorsTransformers.GetUpdateAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetUpdateAsCsv)
    print(output)